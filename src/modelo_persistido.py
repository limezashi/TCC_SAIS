"""Persistencia da RL experimental, exclusivamente para artefatos confiaveis.

Hashes detectam alteracoes, nao autenticam a origem. joblib pode executar codigo:
carregar_modelo exige origem_confiavel=True e pasta dentro de artifacts do projeto.
"""
from datetime import datetime
import hashlib
import io
import json
import math
from numbers import Real
from pathlib import Path
import platform
import re
from zoneinfo import ZoneInfo
import importlib.metadata

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import check_is_fitted

from .modelo_rl import criar_modelo_rl
from .variables import VARIABLES_T0, VARIABLE_TARGET

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "artifacts"
PRODUCER = "TCC_SAIS/rl-experimental"
PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "joblib")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hash_identificadores(ids):
    """SHA-256 de IDs em ordem de treinamento, JSON compacto UTF-8."""
    values = [int(v) for v in ids]
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode("utf-8")).hexdigest()


def versoes():
    return {name: importlib.metadata.version(name) for name in PACKAGES}


def configuracao(modelo):
    return {"steps": list(modelo.named_steps),
            "scaler": modelo.named_steps["scaler"].get_params(),
            "regressao_logistica": modelo.named_steps["regressao_logistica"].get_params()}


def validar_modelo(modelo):
    esperado = criar_modelo_rl()
    if type(modelo) is not Pipeline or list(modelo.named_steps) != list(esperado.named_steps):
        raise ValueError("Artefato nao e a pipeline RL selecionada.")
    for name in esperado.named_steps:
        if type(modelo.named_steps[name]) is not type(esperado.named_steps[name]):
            raise ValueError("Tipo de etapa incompativel.")
        check_is_fitted(modelo.named_steps[name])
    if configuracao(modelo) != configuracao(esperado):
        raise ValueError("Hiperparametros diferentes da configuracao selecionada.")
    if list(modelo.feature_names_in_) != VARIABLES_T0 or modelo.n_features_in_ != 11:
        raise ValueError("Contrato ou ordem das variaveis incompativel.")
    if list(modelo.classes_) != [0, 1]:
        raise ValueError("Classes incompatíveis.")


def salvar_modelo(modelo, pasta, dataset_path, ids_treino, positivos, git_commit=None):
    validar_modelo(modelo)
    pasta = Path(pasta).resolve()
    if not pasta.is_relative_to(ARTIFACT_ROOT.resolve()) or pasta == ARTIFACT_ROOT.resolve():
        raise ValueError("Artefatos devem estar em uma subpasta de artifacts.")
    ids = list(ids_treino)
    if len(ids) != 4684 or len(set(ids)) != 4684 or positivos != 505:
        raise ValueError("Treinamento diferente do conjunto selecionado.")
    pasta.mkdir(parents=True, exist_ok=False)
    with (pasta / "modelo.joblib").open("xb") as file:
        joblib.dump(modelo, file, compress=3)
    metadata = {
        "schema_version": 1, "producer": PRODUCER,
        "purpose": "Demonstracao academica em dados sinteticos; sem validacao clinica",
        "created_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "timezone": "America/Sao_Paulo", "git_commit": git_commit,
        "dataset": {"path": str(Path(dataset_path).resolve()), "sha256": sha256(dataset_path)},
        "training": {"n": len(ids), "positive": positivos,
                     "ids_sha256": hash_identificadores(ids),
                     "ids_encoding": "JSON compacto de inteiros em ordem de treinamento, UTF-8",
                     "test_size": .20, "stratify": VARIABLE_TARGET, "random_state": 42},
        "features": VARIABLES_T0, "target": VARIABLE_TARGET, "classes": [0, 1], "positive_class": 1,
        "configuration": configuracao(modelo), "random_state": 42,
        "python": platform.python_version(), "packages": versoes(),
        "source_sha256": {name: sha256(ROOT / "src" / name) for name in
                          ["modelo_rl.py", "variables.py", "preparacao_dados.py", "modelo_persistido.py"]},
        "artifact": {"filename": "modelo.joblib", "sha256": sha256(pasta / "modelo.joblib")},
    }
    with (pasta / "metadados.json").open("x", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    return pasta


def carregar_modelo(pasta, *, origem_confiavel=False):
    """Nunca usar origem_confiavel=True para arquivos enviados por terceiros."""
    if origem_confiavel is not True:
        raise ValueError("Confirme a origem confiavel do artefato gerado pelo projeto.")
    pasta = Path(pasta).resolve()
    if not pasta.is_relative_to(ARTIFACT_ROOT.resolve()) or pasta == ARTIFACT_ROOT.resolve():
        raise ValueError("Pasta fora do diretorio de artefatos do projeto.")
    metadata = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    expected = {"schema_version": 1, "producer": PRODUCER, "features": VARIABLES_T0,
                "target": VARIABLE_TARGET, "classes": [0, 1], "positive_class": 1,
                "configuration": configuracao(criar_modelo_rl()), "random_state": 42,
                "python": platform.python_version(), "packages": versoes()}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Metadados incompatíveis: {key}")
    t = metadata.get("training", {})
    if (t.get("n"), t.get("positive"), t.get("test_size"), t.get("stratify"), t.get("random_state")) != (4684, 505, .2, VARIABLE_TARGET, 42):
        raise ValueError("Metadados de treinamento incompatíveis.")
    for value in [t.get("ids_sha256"), metadata.get("dataset", {}).get("sha256"), metadata.get("artifact", {}).get("sha256")]:
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
            raise ValueError("Hash ausente ou invalido.")
    if metadata["artifact"].get("filename") != "modelo.joblib":
        raise ValueError("Nome do artefato incompativel.")
    artifact = (pasta / "modelo.joblib").resolve()
    if artifact.parent != pasta:
        raise ValueError("Artefato fora da pasta esperada.")
    payload = artifact.read_bytes()
    if hashlib.sha256(payload).hexdigest() != metadata["artifact"]["sha256"]:
        raise ValueError("Integridade do artefato comprometida.")
    # Carrega os mesmos bytes verificados, evitando troca entre hash e leitura.
    modelo = joblib.load(io.BytesIO(payload))
    validar_modelo(modelo)
    return modelo


def prever_probabilidade(modelo, dados):
    validar_modelo(modelo)
    if not isinstance(dados, dict) or set(dados) != set(VARIABLES_T0):
        raise ValueError("Forneca exatamente as onze variaveis esperadas.")
    for key, value in dados.items():
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"Valor numerico finito obrigatorio: {key}")
    frame = pd.DataFrame([[float(dados[key]) for key in VARIABLES_T0]], columns=VARIABLES_T0)
    positive = int(np.flatnonzero(modelo.classes_ == 1)[0])
    p = float(modelo.predict_proba(frame)[0, positive])
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Probabilidade invalida.")
    return p
