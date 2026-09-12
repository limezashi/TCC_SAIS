from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression


def criar_modelo_rl():
    """
    Cria e retorna o modelo de Regressão Logística.

    O StandardScaler realiza a padronização das variáveis
    antes da aplicação da Regressão Logística.
    """

    modelo = Pipeline([
        ("scaler", StandardScaler()),
        ("regressao_logistica", LogisticRegression(
            max_iter=1000,
            random_state=42
        ))
    ])

    return modelo