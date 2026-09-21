try:
    from .modelo_rl import criar_modelo_rl
    from .modelo_rf import criar_modelo_rf
except ImportError:
    from modelo_rl import criar_modelo_rl
    from modelo_rf import criar_modelo_rf

PESO_RL = 0.90
PESO_RF = 0.10


def criar_modelo_final():
    modelo_rl = criar_modelo_rl()
    modelo_rf = criar_modelo_rf()

    return {"Regressão Logística": modelo_rl, "Random Forest": modelo_rf}


def treinar_modelo_final(X_train, y_train):

    modelos = criar_modelo_final()

    for modelo in modelos.values():
        modelo.fit(X_train, y_train)

    return modelos


def prever_probabilidade(modelos, dados):

    modelo_rl = modelos["Regressão Logística"]
    modelo_rf = modelos["Random Forest"]

    prob_rl = modelo_rl.predict_proba(dados)[:, 1]
    prob_rf = modelo_rf.predict_proba(dados)[:, 1]

    probabilidade_final = PESO_RL * prob_rl + PESO_RF * prob_rf

    return probabilidade_final
