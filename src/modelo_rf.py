from sklearn.ensemble import RandomForestClassifier


def criar_modelo_rf():
    modelo = RandomForestClassifier(
        n_estimators=100,
        random_state=42
    )

    return modelo
    