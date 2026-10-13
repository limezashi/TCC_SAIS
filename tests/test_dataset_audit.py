"""Auditoria somente de leitura. Execute: python -B tests/test_dataset_audit.py

Use --metrics para treinar os estimadores existentes apenas em memoria.
--historical-metrics tambem avalia 47b72f2 em memoria como controle.
Nao grava CSVs, modelos, notebooks ou resultados. Dependencias: pandas e
scikit-learn; --metrics tambem requer xgboost.
"""
import argparse
import collections
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
DATASET = ROOT / "data" / "dataset.csv"


def git(*args):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], encoding="utf-8"
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_frame(frame, target):
    y = frame[target]
    invalid = ~y.isin([0, 1])
    counts = y.value_counts(dropna=False)
    positive_counts = int(counts.get(1, 0))
    positive_sum = int(y.sum()) if not invalid.any() else None
    independent = collections.Counter(
        row[target] for row in csv.DictReader(io.StringIO(frame.to_csv(index=False)))
    )
    if not invalid.any():
        assert positive_counts == positive_sum == independent.get("1", 0)
    return {
        "total": len(frame), "target": target,
        "negative": int(counts.get(0, 0)), "positive_value_counts": positive_counts,
        "positive_sum": positive_sum,
        "prevalence_percent": positive_counts / len(frame) * 100 if len(frame) else None,
        "dtypes": {key: str(value) for key, value in frame.dtypes.items()},
        "missing_by_column": {key: int(value) for key, value in frame.isna().sum().items()},
        "invalid_target_count": int(invalid.sum()),
        "invalid_target_rows": [int(i) + 2 for i in frame.index[invalid]],
    }


def historical_audit(pd):
    versions = []
    previous = None
    for commit in git("log", "--reverse", "--format=%H", "HEAD", "--", "data/dataset.csv").splitlines():
        raw = git("show", commit + ":data/dataset.csv")
        frame = pd.read_csv(io.StringIO(raw)) if raw.strip() else pd.DataFrame()
        entry = {"commit": commit, "subject": git("show", "-s", "--format=%s", commit).strip()}
        if frame.empty:
            entry["total"] = 0
            versions.append(entry)
            continue
        target = "sepsis" if "sepsis" in frame else "sepse"
        entry["summary"] = audit_frame(frame, target)
        if previous is not None:
            old, old_target = previous
            assert old.patient_id.is_unique and frame.patient_id.is_unique
            left = old.set_index("patient_id")
            right = frame.set_index("patient_id")
            common = left.index.intersection(right.index)
            changes = {}
            for column in left.columns.intersection(right.columns):
                a, b = left.loc[common, column], right.loc[common, column]
                changes[column] = int((~(a.eq(b) | (a.isna() & b.isna()))).sum())
            a, b = left.loc[common, old_target], right.loc[common, target]
            entry["comparison_to_previous"] = {
                "same_id_order": old.patient_id.tolist() == frame.patient_id.tolist(),
                "added_ids": len(right.index.difference(left.index)),
                "removed_ids": len(left.index.difference(right.index)),
                "added_columns": sorted(set(frame.columns) - set(old.columns)),
                "removed_columns": sorted(set(old.columns) - set(frame.columns)),
                "changed_common_columns": changes,
                "target_names": [old_target, target],
                "changed_targets": int(a.ne(b).sum()),
                "target_transitions": dict(collections.Counter(f"{x}->{y}" for x, y in zip(a, b))),
            }
        versions.append(entry)
        previous = frame, target
    return versions


def notebook_evidence():
    result = {}
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        nb = json.loads(path.read_text(encoding="utf-8"))
        cells = []
        for i, cell in enumerate(nb["cells"]):
            source = "".join(cell.get("source", []))
            outputs = "".join(
                "".join(o.get("text", [])) + "".join(o.get("data", {}).get("text/plain", []))
                for o in cell.get("outputs", [])
            )
            if any(token in source for token in ["dataset.csv", "read_csv", "preparar_dados("]):
                cells.append({"index": i, "execution_count": cell.get("execution_count"), "source": source})
            if outputs and any(token in source for token in ["resultados_teste", "resultados_finais", "melhor_auc", "melhor_brier"]):
                cells.append({"index": i, "saved_output_not_reproduced": outputs})
        relative = path.relative_to(ROOT).as_posix()
        result[relative] = {
            "sha256": sha(path),
            "last_commit": git("log", "-1", "--format=%H %aI %s", "HEAD", "--", relative).strip(),
            "metadata": nb.get("metadata"), "evidence": cells,
        }
    return result


def evaluate(X_train, X_test, y_train, y_test):
    from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score
    from src.modelos import criar_modelos
    from src.modelo_final import prever_probabilidade

    models = criar_modelos()
    results = {}
    def score(probabilities, predictions):
        matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
        tn, fp, fn, tp = matrix.ravel()
        return {"auc_roc": float(roc_auc_score(y_test, probabilities)),
                "brier": float(brier_score_loss(y_test, probabilities)),
                "sensitivity": float(tp / (tp + fn)),
                "specificity": float(tn / (tn + fp)),
                "confusion_matrix_labels_0_1": matrix.tolist()}
    for name, model in models.items():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(X_train, y_train)
            probability = model.predict_proba(X_test)[:, 1]
            results[name] = score(probability, model.predict(X_test))
            results[name]["warnings"] = [str(w.message) for w in caught]
        results[name]["parameters"] = {k: str(v) for k, v in model.get_params(deep=True).items()}
    probability = prever_probabilidade(models, X_test)
    results["RL + RF (90/10)"] = score(probability, (probability >= 0.5).astype(int))
    results["RL + RF (90/10)"]["classification_threshold_for_audit_only"] = 0.5
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", action="store_true")
    parser.add_argument("--historical-metrics", action="store_true")
    args = parser.parse_args()
    tracked = [ROOT / p for p in git("ls-files").splitlines() if (ROOT / p).is_file()]
    before = {str(path): sha(path) for path in tracked}
    try:
        import pandas as pd
        from src.preparacao_dados import preparar_dados
        from src.variables import VARIABLE_TARGET
        frame = pd.read_csv(DATASET)
        report = {"python": platform.python_version(), "head": git("rev-parse", "HEAD").strip(),
                  "dataset_path": str(DATASET), "dataset_sha256": sha(DATASET),
                  "versions": {name: importlib.metadata.version(name) for name in ["pandas", "numpy", "scikit-learn"]},
                  "current": audit_frame(frame, VARIABLE_TARGET),
                  "history_head": historical_audit(pd), "notebooks": notebook_evidence()}
        independent = collections.Counter(row[VARIABLE_TARGET] for row in csv.DictReader(DATASET.open(encoding="utf-8", newline="")))
        assert report["current"]["positive_value_counts"] == independent.get("1", 0)
        assert report["current"]["invalid_target_count"] == 0
        X_train, X_test, y_train, y_test = preparar_dados(str(DATASET))
        assert set(X_train.index).isdisjoint(X_test.index)
        assert set(X_train.index) | set(X_test.index) == set(frame.index)
        report["split"] = {"procedure": "src.preparacao_dados.preparar_dados",
                           "test_size": 0.20, "random_state": 42, "stratify": VARIABLE_TARGET,
                           "train": audit_frame(frame.loc[X_train.index], VARIABLE_TARGET),
                           "test": audit_frame(frame.loc[X_test.index], VARIABLE_TARGET)}
        if args.metrics or args.historical_metrics:
            report["versions"]["xgboost"] = importlib.metadata.version("xgboost")
            report["metrics_calculated_now"] = evaluate(X_train, X_test, y_train, y_test)
            if args.historical_metrics:
                from sklearn.model_selection import train_test_split
                from src.variables import VARIABLES_T0
                commit = git("rev-parse", "47b72f2").strip()
                historical = pd.read_csv(io.StringIO(git("show", commit + ":data/dataset.csv")))
                split = train_test_split(
                    historical[VARIABLES_T0], historical[VARIABLE_TARGET],
                    test_size=0.20, random_state=42, stratify=historical[VARIABLE_TARGET],
                )
                assert split[0].index.tolist() == X_train.index.tolist()
                assert split[1].index.tolist() == X_test.index.tolist()
                report["historical_metrics_calculated_now"] = {
                    "commit": commit,
                    "same_train_test_indices_as_current": True,
                    "metrics": evaluate(*split),
                }
        else:
            report["metrics_calculated_now"] = "Not requested; use --metrics"
        print(json.dumps(report, ensure_ascii=True, indent=2))
    finally:
        changed = [path for path, digest in before.items() if sha(Path(path)) != digest]
        if changed:
            raise RuntimeError(f"Tracked files changed during audit: {changed}")
        print("Integrity check: all previously tracked files unchanged.", file=sys.stderr)


if __name__ == "__main__":
    main()
