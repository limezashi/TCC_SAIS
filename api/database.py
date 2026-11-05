"""Conexao com o banco de dados PostgreSQL do SAIS."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


# Carrega as configuracoes do arquivo .env na raiz do projeto.
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def obter_conexao():
    """Abre uma conexao com o banco PostgreSQL."""

    configuracao = {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "connect_timeout": 5,
    }

    obrigatorias = ("host", "port", "dbname", "user", "password")

    if any(not configuracao[campo] for campo in obrigatorias):
        raise RuntimeError(
            "Configuracoes do PostgreSQL ausentes no arquivo .env."
        )

    return psycopg.connect(**configuracao)

def salvar_avaliacao(
    patient_id,
    probabilidade,
    modelo_hash,
    entradas_utilizadas,
):
    """Registra uma avaliação sem sobrescrever o histórico anterior."""

    import json

    consulta = """
        INSERT INTO avaliacoes (
            patient_id,
            probabilidade,
            modelo_hash,
            entradas_utilizadas
        )
        VALUES (%s, %s, %s, %s::jsonb)
        RETURNING id, calculado_em;
    """

    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(
                consulta,
                (
                    patient_id,
                    probabilidade,
                    modelo_hash,
                    json.dumps(entradas_utilizadas),
                ),
            )
            resultado = cursor.fetchone()

    return {
        "id": resultado[0],
        "calculado_em": resultado[1].isoformat(),
    }


def paciente_existe(patient_id):
    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pacientes WHERE patient_id = %s;", (patient_id,))
            return cursor.fetchone() is not None


def listar_avaliacoes(patient_id, limite=None):
    consulta = """
        SELECT id, probabilidade, modelo_hash, calculado_em, entradas_utilizadas
        FROM avaliacoes WHERE patient_id = %s
        ORDER BY calculado_em DESC, id DESC
    """
    parametros = [patient_id]
    if limite is not None:
        consulta += " LIMIT %s"
        parametros.append(limite)
    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            rows = cursor.fetchall()
    return [{
        "id": row[0], "probabilidade": row[1], "modelo_hash": row[2],
        "calculado_em": row[3].isoformat(), "entradas_utilizadas": row[4],
    } for row in rows]


def listar_ultimas_avaliacoes():
    """Busca uma unica avaliacao recente por paciente com historico."""
    consulta = """
        SELECT DISTINCT ON (patient_id)
            patient_id, id, probabilidade, modelo_hash, calculado_em
        FROM avaliacoes
        ORDER BY patient_id, calculado_em DESC, id DESC;
    """
    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta)
            rows = cursor.fetchall()
    return [{
        "patient_id": row[0], "id": row[1], "probabilidade": row[2],
        "modelo_hash": row[3], "calculado_em": row[4].isoformat(),
    } for row in rows]


def listar_pacientes_paginados(page=1, page_size=10, search=None, data_avaliacao=None):
    """Consulta uma pagina e sua avaliacao mais recente diretamente no PostgreSQL."""
    filtros = []
    parametros = []
    if search:
        # strpos trata a pesquisa como texto literal, sem curingas de ILIKE.
        filtros.append("strpos(lower(patient_id), lower(%s)) > 0")
        parametros.append(search)
    if data_avaliacao is not None:
        filtros.append("data_avaliacao = %s")
        parametros.append(data_avaliacao)
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    offset = (page - 1) * page_size

    consulta_pagina = f"""
        SELECT p.patient_id, p.data_avaliacao,
               p.pas, p.fc, p.temperatura, p.leucocitos, p.neutrofilos,
               p.rnl, p.bastonetes, p.pao2_fio2, p.creatinina, p.lactato, p.plaquetas,
               ultima.id, ultima.probabilidade, ultima.modelo_hash, ultima.calculado_em
        FROM (
            SELECT patient_id, data_avaliacao, pas, fc, temperatura, leucocitos,
                   neutrofilos, rnl, bastonetes, pao2_fio2, creatinina, lactato, plaquetas
            FROM pacientes
            {where}
            ORDER BY patient_id
            LIMIT %s OFFSET %s
        ) AS p
        LEFT JOIN LATERAL (
            SELECT id, probabilidade, modelo_hash, calculado_em
            FROM avaliacoes
            WHERE patient_id = p.patient_id
            ORDER BY calculado_em DESC, id DESC
            LIMIT 1
        ) AS ultima ON TRUE
        ORDER BY p.patient_id;
    """

    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM pacientes {where};", parametros)
            total = cursor.fetchone()[0]
            cursor.execute(consulta_pagina, [*parametros, page_size, offset])
            rows = cursor.fetchall()

    items = []
    for row in rows:
        if row[1] is None or any(value is None for value in row[2:13]):
            raise ValueError(f"Registro incompleto: {row[0]}.")
        item = {
            "patient_id": row[0],
            "data_avaliacao": row[1],
            **{name: float(value) for name, value in zip(
                ("pas", "fc", "temperatura", "leucocitos", "neutrofilos", "rnl",
                 "bastonetes", "pao2_fio2", "creatinina", "lactato", "plaquetas"),
                row[2:13],
            )},
            "ultima_avaliacao": None,
        }
        if row[13] is not None:
            item["ultima_avaliacao"] = {
                "id": row[13],
                "probabilidade": row[14],
                "modelo_hash": row[15],
                "calculado_em": row[16].isoformat(),
            }
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
