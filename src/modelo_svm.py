from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


def criar_modelo_svm():

    # Cada fold interno ajusta sua propria padronizacao.
    modelo = CalibratedClassifierCV(
        estimator=Pipeline([
            ("scaler", StandardScaler()),
            ("svm", SVC(random_state=42)),
        ]),
        cv=5,
        ensemble=False,
    )

    return modelo
