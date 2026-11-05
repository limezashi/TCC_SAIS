"""Leitura dos pacientes demonstrativos armazenados no PostgreSQL."""

from .database import obter_conexao
from src.variables import VARIABLES_T0


def carregar_pacientes():
    """Consulta os 30 pacientes demonstrativos no banco de dados."""

    colunas = ["patient_id", "data_avaliacao", *VARIABLES_T0]
    consulta = f"""
        SELECT {", ".join(colunas)}
        FROM pacientes
        WHERE patient_id LIKE 'DEMO%'
        ORDER BY patient_id;
    """

    with obter_conexao() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta)
            registros = cursor.fetchall()

    if len(registros) != 30:
        raise ValueError(
            f"Esperados 30 pacientes demonstrativos; encontrados {len(registros)}."
        )

    pacientes = []

    for registro in registros:
        paciente = dict(zip(colunas, registro))

        if any(paciente[campo] is None for campo in colunas):
            raise ValueError(
                f"Registro incompleto: {paciente['patient_id']}."
            )

        paciente["data_avaliacao"] = paciente["data_avaliacao"].isoformat()

        for campo in VARIABLES_T0:
            paciente[campo] = float(paciente[campo])

        pacientes.append(paciente)

    return pacientes