"""Avaliacao final unica da RL persistida no conjunto de teste.

Pre-registro: modelo rl_20261014T100407101829_b83773b9, sem reajuste;
Brier, ROC-AUC, IC95% por bootstrap estratificado (5000, semente 20261026),
calibracao por decis. O teste ja foi consultado em notebooks anteriores:
este resultado nao orienta ajustes nem nova selecao.
Roda uma unica vez (aborta se o resultado ja existir).
"""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import roc_auc_score

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preparacao_dados import preparar_dados
from src.modelo_persistido import carregar_modelo, hash_identificadores

PASTA = ROOT / "artifacts" / "rl_20261014T100407101829_b83773b9"
SAIDA = ROOT / "execucao_referencia" / "teste_final_rl.json"
HASH_DATASET = "0ffe90627e19a05c4d25ad747fe19d5766e7a1080dff512e98679d5330d196ca"
HASH_MODELO = "87130c15c8eb66d1242c6fa731cc5b2da081eb79e3547eeead4a7d936cdd8ccc"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if SAIDA.exists():
        sys.exit("Resultado ja existe: a avaliacao final roda uma unica vez.")

    dataset = ROOT / "data" / "dataset.csv"
    assert sha(dataset) == HASH_DATASET, "dataset diferente do registrado"
    assert sha(PASTA / "modelo.joblib") == HASH_MODELO, "modelo diferente do registrado"

    X_tr, X_te, y_tr, y_te = preparar_dados(str(dataset))
    assert (len(X_tr), int(y_tr.sum())) == (4684, 505), "treino inesperado"
    assert len(X_te) == 1171, "teste inesperado"
    assert np.intersect1d(X_tr.index, X_te.index).size == 0, "treino e teste se sobrepoem"

    ids = pd.read_csv(dataset, usecols=["patient_id"]).loc[X_tr.index, "patient_id"]
    meta = json.loads((PASTA / "metadados.json").read_text(encoding="utf-8"))
    assert hash_identificadores(ids) == meta["training"]["ids_sha256"], "treino diferente do registrado"

    modelo = carregar_modelo(PASTA, origem_confiavel=True)
    pos = int(np.flatnonzero(modelo.classes_ == 1)[0])
    p = modelo.predict_proba(X_te)[:, pos]
    y = y_te.to_numpy()

    brier = float(np.mean((p - y) ** 2))
    auc = float(roc_auc_score(y, p))
    prev_treino = 505 / 4684
    brier_ref = float(np.mean((prev_treino - y) ** 2))

    rng = np.random.default_rng(20261026)
    ip, ineg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    bs, ba = [], []
    for _ in range(5000):
        i = np.concatenate([rng.choice(ip, len(ip)), rng.choice(ineg, len(ineg))])
        bs.append(float(np.mean((p[i] - y[i]) ** 2)))
        ba.append(float(roc_auc_score(y[i], p[i])))
    ic = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]

    tab = pd.DataFrame({"p": p, "y": y})
    tab["grupo"] = pd.qcut(tab["p"], 10, duplicates="drop")
    cal = (tab.groupby("grupo", observed=True)
              .agg(n=("y", "size"), prob_media=("p", "mean"), taxa_observada=("y", "mean"))
              .reset_index(drop=True))

    res = {
        "aviso": "Avaliacao unica em dados sinteticos. O conjunto de teste ja havia sido "
                 "consultado em notebooks anteriores; nao e validacao independente nem clinica.",
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "modelo": PASTA.name,
        "n_teste": int(len(y)),
        "positivos_teste": int(y.sum()),
        "prevalencia_teste": float(y.mean()),
        "brier": brier,
        "brier_ic95_bootstrap": ic(bs),
        "brier_referencia_prevalencia_treino": brier_ref,
        "brier_skill_score": 1 - brier / brier_ref,
        "roc_auc": auc,
        "roc_auc_ic95_bootstrap": ic(ba),
        "bootstrap": {"n": 5000, "semente": 20261026, "estratificado": True},
        "calibracao_decis": cal.to_dict(orient="records"),
        "ambiente": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "git_commit": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
            "sha256_script": sha(__file__),
            "sha256_dataset": HASH_DATASET,
            "sha256_modelo": HASH_MODELO,
        },
    }
    with open(SAIDA, "x", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print(f"n={len(y)} positivos={int(y.sum())} prevalencia={y.mean():.4f}")
    print(f"Brier={brier:.5f} IC95%={ic(bs)} | referencia={brier_ref:.5f} | BSS={1 - brier / brier_ref:.4f}")
    print(f"ROC-AUC={auc:.4f} IC95%={ic(ba)}")
    print(cal.to_string())
    print(f"Salvo em {SAIDA}")


if __name__ == "__main__":
    main()