import pandas as pd

from sklearn.model_selection import train_test_split

try:
    from .variables import VARIABLES_T0, VARIABLE_TARGET
except ImportError:
    from variables import VARIABLES_T0, VARIABLE_TARGET


def carregar_dados(caminho="../data/dataset.csv"):
    df = pd.read_csv(caminho)

    return df


def preparar_dados(caminho="../data/dataset.csv"):

    df = carregar_dados(caminho)

    # Verifica se todas as colunas esperadas existem
    colunas_esperadas = VARIABLES_T0 + [VARIABLE_TARGET, "patient_id"]

    colunas_faltantes = [
        coluna for coluna in colunas_esperadas if coluna not in df.columns
    ]

    if colunas_faltantes:
        raise ValueError(f"Colunas ausentes no dataset: {colunas_faltantes}")

    # Variáveis de entrada
    X = df[VARIABLES_T0]

    # Variável alvo
    y = df[VARIABLE_TARGET]

    # Separação entre treino e teste
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    return X_train, X_test, y_train, y_test
