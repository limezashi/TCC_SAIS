try:
    from .modelo_rl import criar_modelo_rl
    from .modelo_rf import criar_modelo_rf
    from .modelo_xgb import criar_modelo_xgb
    from .modelo_svm import criar_modelo_svm
except ImportError:
    from modelo_rl import criar_modelo_rl
    from modelo_rf import criar_modelo_rf
    from modelo_xgb import criar_modelo_xgb
    from modelo_svm import criar_modelo_svm


def criar_modelos():

    modelos = {
        "Regressão Logística": criar_modelo_rl(),
        "Random Forest": criar_modelo_rf(),
        "XGBoost": criar_modelo_xgb(),
        "SVM": criar_modelo_svm(),
    }

    return modelos
