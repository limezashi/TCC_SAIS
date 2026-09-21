from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import (
    roc_auc_score,
    confusion_matrix,
    classification_report,
    brier_score_loss,
)


def treinar_modelos(modelos, X_train, y_train):

    modelos_treinados = {}

    for nome, modelo in modelos.items():

        modelo.fit(X_train, y_train)

        modelos_treinados[nome] = modelo

    return modelos_treinados


def validar_modelos(modelos, X_train, y_train):

    resultados = {}

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for nome, modelo in modelos.items():

        scores_auc = cross_val_score(modelo, X_train, y_train, cv=cv, scoring="roc_auc")

        scores_brier = -cross_val_score(
            modelo, X_train, y_train, cv=cv, scoring="neg_brier_score"
        )

        resultados[nome] = {
            "scores_auc": scores_auc,
            "media_auc": scores_auc.mean(),
            "desvio_auc": scores_auc.std(),
            "scores_brier": scores_brier,
            "media_brier": scores_brier.mean(),
            "desvio_brier": scores_brier.std(),
        }

    return resultados


def avaliar_modelos(modelos, X_test, y_test):

    resultados = {}

    for nome, modelo in modelos.items():

        probabilidades = modelo.predict_proba(X_test)[:, 1]

        predicoes = modelo.predict(X_test)

        auc = roc_auc_score(y_test, probabilidades)

        brier = brier_score_loss(y_test, probabilidades)

        matriz = confusion_matrix(y_test, predicoes)

        relatorio = classification_report(y_test, predicoes, output_dict=True)

        resultados[nome] = {
            "probabilidades": probabilidades,
            "predicoes": predicoes,
            "auc": auc,
            "brier": brier,
            "matriz_confusao": matriz,
            "relatorio": relatorio,
        }

    return resultados
