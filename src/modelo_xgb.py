from xgboost import XGBClassifier


def criar_modelo_xgb():

    modelo = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")

    return modelo
