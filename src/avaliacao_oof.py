"""Avaliacao de candidatos fixos exclusivamente sobre dados de treinamento."""
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (brier_score_loss, confusion_matrix, f1_score,
                             precision_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold

RL = "Regressão Logística"
RF = "Random Forest"
ENSEMBLE = "RL + RF (90/10)"
BASELINE = "Prevalência do treinamento do fold"
PESO_RL, PESO_RF = 0.90, 0.10


def classificar(y, probabilidades, limiar=0.5):
    pred = (np.asarray(probabilidades) >= limiar).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"limiar": float(limiar), "sensibilidade": float(tp / (tp + fn)),
            "especificidade": float(tn / (tn + fp)),
            "precisao": float(precision_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
            "positivos_preditos": int(pred.sum()),
            "matriz_confusao": [[int(tn), int(fp)], [int(fn), int(tp)]]}


def curva_calibracao(y, p, n_bins=10):
    """Grupos por quantis; limites repetidos sao colapsados (inclui constante)."""
    y, p = np.asarray(y), np.asarray(p)
    bounds = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    groups = np.searchsorted(bounds[1:-1], p, side="right")
    return [{"grupo": int(g), "n": int((groups == g).sum()),
             "probabilidade_media": float(p[groups == g].mean()),
             "frequencia_observada": float(y[groups == g].mean())}
            for g in np.unique(groups)]


def avaliar_oof(X, y, modelos, patient_ids, n_splits=5, random_state=42,
                progresso=None):
    """Nao recebe conjunto de teste. Clona e ajusta em folds compartilhados."""
    if len(X) != len(y) or len(X) != len(patient_ids):
        raise ValueError("Entradas, alvo e identificadores devem estar alinhados.")
    if not X.index.equals(y.index) or not X.index.is_unique:
        raise ValueError("Indices de X e y devem ser iguais e unicos.")
    if isinstance(patient_ids, pd.Series) and not X.index.equals(patient_ids.index):
        raise ValueError("Identificadores desalinhados.")
    if set(np.unique(y)) != {0, 1} or y.value_counts().min() < n_splits:
        raise ValueError("Alvo binario e classes suficientes por fold sao obrigatorios.")
    if RL not in modelos or RF not in modelos or ENSEMBLE in modelos or BASELINE in modelos:
        raise ValueError("Candidatos devem incluir RL/RF e excluir nomes reservados.")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    nomes = list(modelos) + [ENSEMBLE, BASELINE]
    probs = {nome: np.full(len(y), np.nan) for nome in nomes}
    cobertura = np.zeros(len(y), dtype=int)
    folds = np.zeros(len(y), dtype=int)
    metricas, particoes, avisos = [], [], []
    for fold, (it, iv) in enumerate(cv.split(X, y), 1):
        if np.intersect1d(it, iv).size:
            raise RuntimeError("Sobreposicao entre treino e validacao.")
        cobertura[iv] += 1
        folds[iv] = fold
        particoes.append({"fold": fold, "posicoes_treino": it.tolist(),
                          "posicoes_validacao": iv.tolist(),
                          "n_treino": len(it), "n_validacao": len(iv),
                          "positivos_treino": int(y.iloc[it].sum()),
                          "positivos_validacao": int(y.iloc[iv].sum())})
        for nome, base in modelos.items():
            if progresso:
                progresso(f"Fold {fold}/{n_splits}: {nome}")
            modelo = clone(base)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                modelo.fit(X.iloc[it], y.iloc[it])
                classe = np.flatnonzero(modelo.classes_ == 1)
                p = modelo.predict_proba(X.iloc[iv])[:, int(classe[0])]
            if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
                raise RuntimeError(f"Probabilidades invalidas: {nome}")
            probs[nome][iv] = p
            avisos.extend({"fold": fold, "modelo": nome, "aviso": str(w.message)} for w in caught)
        probs[ENSEMBLE][iv] = PESO_RL * probs[RL][iv] + PESO_RF * probs[RF][iv]
        probs[BASELINE][iv] = float(y.iloc[it].mean())
        for nome in nomes:
            metricas.append({"modelo": nome, "fold": fold,
                             "auc": float(roc_auc_score(y.iloc[iv], probs[nome][iv])),
                             "brier": float(brier_score_loss(y.iloc[iv], probs[nome][iv]))})
    if not np.all(cobertura == 1) or any(np.isnan(p).any() for p in probs.values()):
        raise RuntimeError("Cobertura OOF incompleta ou duplicada.")
    tabela = pd.DataFrame(metricas)
    oof = pd.DataFrame({"row_index": X.index, "patient_id": np.asarray(patient_ids),
                        "fold": folds, "sepsis": np.asarray(y), **probs})
    resumo, limiares, calibracao = {}, [], []
    for nome in nomes:
        p, linhas = probs[nome], tabela[tabela.modelo == nome]
        resumo[nome] = {
            "auc_media": float(linhas.auc.mean()), "auc_dp_ddof0": float(linhas.auc.std(ddof=0)),
            "brier_media": float(linhas.brier.mean()), "brier_dp_ddof0": float(linhas.brier.std(ddof=0)),
            "auc_oof": float(roc_auc_score(y, p)), "brier_oof": float(brier_score_loss(y, p)),
            "classificacao_05": classificar(y, p),
            "distribuicao": {"min": float(p.min()), "max": float(p.max()),
                              "media": float(p.mean()), "dp": float(p.std()),
                              "quantis": dict(zip(["p01", "p05", "p25", "p50", "p75", "p90", "p95", "p99"],
                                                  map(float, np.quantile(p, [.01, .05, .25, .5, .75, .9, .95, .99]))))},
            "distribuicao_por_classe": {
                str(c): {"n": int((np.asarray(y) == c).sum()),
                         "media": float(p[np.asarray(y) == c].mean()),
                         "mediana": float(np.median(p[np.asarray(y) == c]))} for c in [0, 1]},
        }
        for ponto in curva_calibracao(y, p):
            calibracao.append({"modelo": nome, **ponto})
        for t in [0, .025, .05, .075, .10, .125, .15, .20, .25, .30, .40, .50, .75, 1.0]:
            limiares.append({"modelo": nome, **classificar(y, p, t)})
    rl, ens = tabela[tabela.modelo == RL].set_index("fold"), tabela[tabela.modelo == ENSEMBLE].set_index("fold")
    pareadas = pd.DataFrame({"fold": rl.index,
                            "delta_auc_ensemble_menos_rl": (ens.auc - rl.auc).values,
                            "delta_brier_ensemble_menos_rl": (ens.brier - rl.brier).values})
    return {"resumo": resumo, "oof": oof, "metricas_folds": tabela,
            "diferencas_pareadas": pareadas, "limiares": pd.DataFrame(limiares),
            "calibracao": pd.DataFrame(calibracao), "particoes": particoes, "avisos": avisos}
