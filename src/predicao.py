import pandas as pd

try:
    from .modelo_final import treinar_modelo_final, prever_probabilidade
    from .variables import VARIABLES_T0
except ImportError:
    from modelo_final import treinar_modelo_final, prever_probabilidade
    from variables import VARIABLES_T0


def treinar(X_train, y_train):

    modelos = treinar_modelo_final(X_train, y_train)

    return modelos


def prever(modelos, dados):

    dados_df = pd.DataFrame([dados])

    dados_df = dados_df[VARIABLES_T0]

    probabilidade = prever_probabilidade(modelos, dados_df)

    return float(probabilidade[0])
