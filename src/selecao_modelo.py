"""Incerteza condicional pareada sobre previsoes OOF fixas."""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def bootstrap_pareado(y, p_referencia, p_candidato, n_bootstrap=5000, seed=20261013):
    y, a, b = map(np.asarray, (y, p_referencia, p_candidato))
    if not (y.ndim == a.ndim == b.ndim == 1 and len(y) == len(a) == len(b)):
        raise ValueError("Vetores devem ser unidimensionais e alinhados.")
    if set(np.unique(y)) != {0, 1} or n_bootstrap < 2:
        raise ValueError("Duas classes e pelo menos duas reamostragens obrigatorias.")
    if not (np.isfinite(a).all() and np.isfinite(b).all()) or ((a < 0) | (a > 1) | (b < 0) | (b > 1)).any():
        raise ValueError("Probabilidades invalidas.")
    rng = np.random.default_rng(seed)
    classes = [np.flatnonzero(y == c) for c in [0, 1]]
    loss_delta = (b - y)**2 - (a - y)**2
    rows = []
    for i in range(n_bootstrap):
        idx = np.concatenate([rng.choice(c, size=len(c), replace=True) for c in classes])
        rows.append({"reamostragem": i + 1, "delta_brier": float(loss_delta[idx].mean()),
                     "delta_auc": float(roc_auc_score(y[idx], b[idx]) - roc_auc_score(y[idx], a[idx]))})
    samples = pd.DataFrame(rows)
    summary = {"seed": seed, "n_bootstrap": n_bootstrap, "stratified": True,
               "definition": "candidato menos referencia; Brier negativo favorece candidato",
               "limitations": "Condicional as previsoes fixas; nao reajusta modelos; preserva prevalencia; nao inclui toda variabilidade do treinamento ou selecao; folds e repeticoes dependentes."}
    for metric, observed in [("brier", float(loss_delta.mean())),
                             ("auc", float(roc_auc_score(y, b) - roc_auc_score(y, a)))]:
        values = samples["delta_" + metric]
        summary[metric] = {"observed_delta": observed,
                           "percentile_interval_95": list(map(float, np.quantile(values, [.025, .975]))),
                           "fraction_candidate_better": float((values < 0).mean() if metric == "brier" else (values > 0).mean())}
    return summary, samples
