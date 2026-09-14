# separar X e y;dividir treino/teste; eventualmente tratar valores ausentes;garantir que as 9 variáveis estejam presentes.

import pandas as pd
from sklearn.model_selection import train_test_split

from src.variables import VARIABLES_T0


def preparar_dados(caminho):

    dados = pd.read_csv(caminho)

    # Verifica se todas as variáveis esperadas estão presentes
    colunas_necessarias = VARIABLES_T0 + ["risco"]

    colunas_faltantes = [
        coluna for coluna in colunas_necessarias if coluna not in dados.columns
    ]

    if colunas_faltantes:
        raise ValueError(f"Colunas ausentes no dataset: {colunas_faltantes}")

    # Separa variáveis de entrada (X) e variável-alvo (y)
    X = dados[VARIABLES_T0]
    y = dados["risco"]

    # Divide os dados em treinamento e teste
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    return X_train, X_test, y_train, y_test
