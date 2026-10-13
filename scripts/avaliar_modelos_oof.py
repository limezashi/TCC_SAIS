"""Execute com python -B scripts/avaliar_modelos_oof.py (somente treinamento)."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plots(result, folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from src.avaliacao_oof import BASELINE
    candidates = [n for n in result["resumo"] if n != BASELINE]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Referencia ideal")
    for name, group in result["calibracao"].groupby("modelo", sort=False):
        ax.plot(group.probabilidade_media, group.frequencia_observada, "o-", label=name)
    ax.set(xlabel="Probabilidade OOF media", ylabel="Frequencia observada", title="Calibracao OOF — dados sinteticos")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(folder / "calibracao.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(len(candidates), 1, figsize=(9, 14))
    for ax, name in zip(axes, candidates):
        for c in [0, 1]:
            ax.hist(result["oof"].loc[result["oof"].sepsis == c, name], bins=25,
                    range=(0, 1), alpha=.5, density=True, label=f"Desfecho {c}")
        ax.set(title=name, xlabel="Probabilidade OOF", ylabel="Densidade"); ax.legend()
    fig.tight_layout(); fig.savefig(folder / "probabilidades.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for name in candidates:
        group = result["limiares"][result["limiares"].modelo == name]
        axes[0].plot(group.limiar, group.sensibilidade, "o-", label=name)
        axes[1].plot(group.limiar, group.especificidade, "o-", label=name)
    for ax, title in zip(axes, ["Sensibilidade", "Especificidade"]):
        ax.set(xlabel="Limiar descritivo", ylabel=title, ylim=(0, 1.02)); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(folder / "limiares_descritivos.png", dpi=160); plt.close(fig)


def main():
    import numpy as np
    import pandas as pd
    from src.preparacao_dados import preparar_dados
    from src.modelos import criar_modelos
    from src.variables import VARIABLES_T0, VARIABLE_TARGET
    from src.avaliacao_oof import avaliar_oof
    protected = [ROOT / "data/dataset.csv", ROOT / "src/modelo_final.py",
                 ROOT / "src/preparacao_dados.py", ROOT / "src/variables.py",
                 *sorted((ROOT / "notebooks").glob("*.ipynb"))]
    before = {str(p): digest(p) for p in protected}
    dataset = ROOT / "data/dataset.csv"
    # Reutiliza exatamente a divisao existente. As parcelas de teste sao descartadas.
    X_train, X_test, y_train, y_test = preparar_dados(str(dataset))
    test_indices = X_test.index.copy()
    del X_test, y_test
    if len(X_train) != 4684 or int(y_train.sum()) != 505:
        raise ValueError("Conjunto de treinamento diferente da base auditada.")
    frame = pd.read_csv(dataset, usecols=["patient_id"])
    ids = frame.loc[X_train.index, "patient_id"]
    del frame
    models = criar_modelos()
    result = avaliar_oof(X_train, y_train, models, ids,
                         progresso=lambda msg: print(msg, flush=True))
    if np.intersect1d(result["oof"].row_index, test_indices).size:
        raise RuntimeError("OOF inclui indices reservados ao teste.")
    timestamp = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%dT%H%M%S%f")
    folder = ROOT / "results" / ("oof_" + timestamp)
    folder.mkdir(parents=True, exist_ok=False)
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        metadata = {"status": "running", "created_at": timestamp, "timezone": "America/Sao_Paulo",
                    "dataset": {"path": str(dataset), "sha256": digest(dataset)},
                    "commit": commit, "python": platform.python_version(),
                    "packages": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
                    "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in
                                      [*sorted((ROOT / "src").glob("*.py")), Path(__file__)]},
                    "configuration": {"n_splits": 5, "shuffle": True, "random_state": 42,
                                      "split_test_size": .2, "split_random_state": 42, "split_stratify": VARIABLE_TARGET,
                                      "n_training": len(y_train), "positive_training": int(y_train.sum()),
                                      "features": VARIABLES_T0, "target": VARIABLE_TARGET,
                                      "weights": {"RL": .9, "RF": .1}, "primary_metric": "brier",
                                      "secondary_metric": "auc", "std_ddof": 0,
                                      "threshold_selection": "none", "test_evaluation": False,
                                      "calibration_bins": "10 quantiles, duplicate edges collapsed"},
                    "model_parameters": {n: {k: repr(v) for k, v in m.get_params(deep=True).items()} for n, m in models.items()},
                    "warnings": result["avisos"]}
        (folder / "metadados.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        for key in ["oof", "metricas_folds", "diferencas_pareadas", "limiares", "calibracao"]:
            result[key].to_csv(folder / (key + ".csv"), index=False)
        (folder / "resumo.json").write_text(json.dumps(result["resumo"], ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "particoes.json").write_text(json.dumps(result["particoes"], indent=2), encoding="utf-8")
        (folder / "requirements-execucao.txt").write_text("\n".join(f"{k}=={v}" for k, v in metadata["packages"].items()) + "\n", encoding="utf-8")
        plots(result, folder)
        changed = [p for p, h in before.items() if digest(Path(p)) != h]
        if changed:
            raise RuntimeError(f"Arquivos protegidos alterados: {changed}")
        metadata["status"] = "completed"
        metadata["protected_files_unchanged"] = True
        metadata["artifact_sha256"] = {p.name: digest(p) for p in folder.iterdir() if p.name != "metadados.json"}
        (folder / "metadados.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print("RESULTS=" + str(folder), flush=True)
    except Exception as exc:
        (folder / "erro.txt").write_text(repr(exc), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
