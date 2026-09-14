from sklearn.model_selection import cross_val_score
from sklearn.metrics import roc_auc_score, confusion_matrix, classification_report


def treinar_modelos(modelos, X_train, y_train):

    modelos_treinados = {}

    for nome, modelo in modelos.items():

        modelo.fit(X_train, y_train)

        modelos_treinados[nome] = modelo

    return modelos_treinados


def validar_modelos(modelos, X, y):

    resultados = {}

    for nome, modelo in modelos.items():

        scores = cross_val_score(modelo, X, y, cv=5, scoring="roc_auc")

        resultados[nome] = {"scores": scores, "media_auc": scores.mean()}

    return resultados


def avaliar_modelos(modelos, X_test, y_test):

    resultados = {}

    for nome, modelo in modelos.items():

        probabilidades = modelo.predict_proba(X_test)[:, 1]
        predicoes = modelo.predict(X_test)

        auc = roc_auc_score(y_test, probabilidades)

        matriz = confusion_matrix(y_test, predicoes)

        relatorio = classification_report(y_test, predicoes, output_dict=True)

        resultados[nome] = {
            "probabilidades": probabilidades,
            "predicoes": predicoes,
            "auc": auc,
            "matriz_confusao": matriz,
            "relatorio": relatorio,
        }

    return resultados
