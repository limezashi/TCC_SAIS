"""Bootstrap pareado e CV repetida, exclusivamente no treinamento existente."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ORIGINAL = ROOT / "results/oof_20261013T133250634327"
SEEDS = [42, 43, 44, 45, 46]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import numpy as np
    import pandas as pd
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from src.preparacao_dados import preparar_dados
    from src.modelos import criar_modelos
    from src.avaliacao_oof import avaliar_oof, RL, RF, ENSEMBLE, BASELINE
    from src.selecao_modelo import bootstrap_pareado
    metadata = json.loads((ORIGINAL / "metadados.json").read_text(encoding="utf-8"))
    if metadata["status"] != "completed":
        raise ValueError("Execucao original incompleta.")
    for name, expected in metadata["artifact_sha256"].items():
        if sha(ORIGINAL / name) != expected:
            raise ValueError(f"Artefato original alterado: {name}")
    dataset = ROOT / "data/dataset.csv"
    if sha(dataset) != metadata["dataset"]["sha256"]:
        raise ValueError("Dataset diferente da execucao original.")
    for name, expected in metadata["source_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Fonte usada na execucao original mudou: {name}")
    for name in ["numpy", "pandas", "scikit-learn", "xgboost"]:
        if importlib.metadata.version(name) != metadata["packages"][name]:
            raise ValueError(f"Ambiente diferente: {name}")
    protected = [*sorted((ROOT / "data").glob("*.csv")), *sorted((ROOT / "src").glob("*.py")),
                 *sorted((ROOT / "notebooks").glob("*.ipynb")),
                 *[p for p in ORIGINAL.rglob("*") if p.is_file()]]
    before = {str(p): sha(p) for p in protected}
    X, xt, y, yt = preparar_dados(str(dataset))
    test_indices = xt.index.copy()
    del xt, yt
    ids = pd.read_csv(dataset, usecols=["patient_id"]).loc[X.index, "patient_id"]
    oof = pd.read_csv(ORIGINAL / "oof.csv")
    assert len(oof) == len(X) == 4684 and int(y.sum()) == 505
    np.testing.assert_array_equal(oof.row_index, X.index)
    np.testing.assert_array_equal(oof.patient_id, ids)
    np.testing.assert_array_equal(oof.sepsis, y)
    assert not np.intersect1d(oof.row_index, test_indices).size
    np.testing.assert_allclose(oof[ENSEMBLE], .9*oof[RL]+.1*oof[RF], rtol=0, atol=1e-14)
    original_summary = json.loads((ORIGINAL / "resumo.json").read_text(encoding="utf-8"))
    for name, values in original_summary.items():
        np.testing.assert_allclose(brier_score_loss(y, oof[name]), values["brier_oof"], atol=1e-14, rtol=0)
        np.testing.assert_allclose(roc_auc_score(y, oof[name]), values["auc_oof"], atol=1e-14, rtol=0)
    folder = ROOT / "results" / ("selecao_" + datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%dT%H%M%S%f"))
    folder.mkdir(parents=True, exist_ok=False)
    protocol = {"primary": "Brier", "secondary": "AUC", "seeds": SEEDS,
                "n_folds": 5, "bootstrap_seed": 20261013, "n_bootstrap": 5000,
                "weights": [0.9, 0.1], "hyperparameter_search": False, "test_evaluation": False,
                "criterion": "Melhor Brier; AUC e calibracao secundarias. Diferenca incerta e sinal instavel: menor complexidade entre candidatos nao distinguiveis. Sem margem clinica ou teste de equivalencia.",
                "fixed_before_execution": True}
    write_json(folder / "protocolo.json", protocol)
    print("Integridade confirmada. Bootstrap pareado de 5000 amostras.", flush=True)
    boot, samples = bootstrap_pareado(y, oof[RL], oof[ENSEMBLE])
    write_json(folder / "bootstrap_resumo.json", boot)
    samples.to_csv(folder / "bootstrap_amostras.csv", index=False)
    print(json.dumps(boot, ensure_ascii=True), flush=True)
    inconclusive = boot["brier"]["percentile_interval_95"][0] <= 0 <= boot["brier"]["percentile_interval_95"][1]
    seeds = SEEDS if inconclusive else [42]
    summary_rows, fold_rows, pair_rows, calibration_rows, warnings = [], [], [], [], []
    for seed in seeds:
        print(f"Repeticao seed={seed}", flush=True)
        if seed == 42:
            summary = original_summary
            folds = pd.read_csv(ORIGINAL / "metricas_folds.csv")
            pairs = pd.read_csv(ORIGINAL / "diferencas_pareadas.csv")
            calibration = pd.read_csv(ORIGINAL / "calibracao.csv")
            partitions = json.loads((ORIGINAL / "particoes.json").read_text(encoding="utf-8"))
            probabilities = oof
        else:
            result = avaliar_oof(X, y, criar_modelos(), ids, random_state=seed,
                                 progresso=lambda msg: print(msg, flush=True))
            summary, folds, pairs, calibration = (result[k] for k in ["resumo", "metricas_folds", "diferencas_pareadas", "calibracao"])
            partitions, probabilities = result["particoes"], result["oof"]
            warnings.extend({"seed": seed, **w} for w in result["avisos"])
        assert not np.intersect1d(probabilities.row_index, test_indices).size
        probabilities.to_csv(folder / f"oof_seed_{seed}.csv", index=False)
        write_json(folder / f"particoes_seed_{seed}.json", partitions)
        for name, values in summary.items():
            summary_rows.append({"seed": seed, "modelo": name, "brier_oof": values["brier_oof"],
                                 "auc_oof": values["auc_oof"], "brier_media_folds": values["brier_media"],
                                 "auc_media_folds": values["auc_media"]})
        fold_rows.append(folds.assign(seed=seed)); pair_rows.append(pairs.assign(seed=seed))
        calibration_rows.append(calibration.assign(seed=seed))
    repeats = pd.DataFrame(summary_rows)
    folds = pd.concat(fold_rows, ignore_index=True)
    pairs = pd.concat(pair_rows, ignore_index=True)
    calibration = pd.concat(calibration_rows, ignore_index=True)
    ranking = repeats.groupby("modelo").agg(
        brier_media=("brier_oof", "mean"), brier_dp=("brier_oof", lambda s: s.std(ddof=0)),
        brier_min=("brier_oof", "min"), brier_max=("brier_oof", "max"),
        auc_media=("auc_oof", "mean"), auc_dp=("auc_oof", lambda s: s.std(ddof=0))).reset_index()
    ranking = ranking.sort_values(["brier_media", "auc_media"], ascending=[True, False])
    rl = repeats[repeats.modelo == RL].set_index("seed")
    ens = repeats[repeats.modelo == ENSEMBLE].set_index("seed")
    deltas = pd.DataFrame({"seed": rl.index, "delta_brier": (ens.brier_oof-rl.brier_oof).values,
                           "delta_auc": (ens.auc_oof-rl.auc_oof).values})
    for name, frame in [("resumo_repeticoes", repeats), ("ranking", ranking), ("metricas_folds", folds),
                        ("diferencas_pareadas_folds", pairs), ("diferencas_pareadas_repeticoes", deltas), ("calibracao", calibration)]:
        frame.to_csv(folder / (name + ".csv"), index=False)
    write_json(folder / "metadados.json", {"status": "completed", "integrity_original": True,
                "original_folder": str(ORIGINAL), "dataset_sha256": sha(dataset),
                "python": platform.python_version(), "packages": metadata["packages"], "warnings": warnings,
                "executed_seeds": seeds, "reused_seed_42": True,
                "bootstrap_triggered_repetition": bool(inconclusive),
                "sources_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [*sorted((ROOT / "src").glob("*.py")), Path(__file__)]},
                "limitations": "Repeticoes e folds nao independentes; bootstrap condicional; sem validade clinica ou equivalencia estatistica."})
    assert all(sha(Path(p)) == h for p, h in before.items()), "Arquivo protegido alterado"
    print(ranking.to_string(index=False), flush=True)
    print(deltas.to_string(index=False), flush=True)
    print("RESULTS=" + str(folder), flush=True)


if __name__ == "__main__":
    main()
