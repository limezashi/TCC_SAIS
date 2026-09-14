from sklearn.svm import SVC


def criar_modelo_svm():

    modelo = SVC(probability=True, random_state=42)

    return modelo
