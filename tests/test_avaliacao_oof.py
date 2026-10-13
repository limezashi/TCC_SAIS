"""Testes de integridade da avaliacao: python -B -m unittest discover -s tests -p test_avaliacao_oof.py"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from src.avaliacao_oof import avaliar_oof, RL, RF, ENSEMBLE, BASELINE
from src.modelo_svm import criar_modelo_svm


class RecordingScaler(StandardScaler):
    fits = []
    def fit(self, X, y=None, **params):
        result = super().fit(X, y, **params)
        self.fits.append((set(X.index), self.mean_.copy()))
        return result


class TestOOF(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.X = pd.DataFrame({"a": rng.normal(size=100), "b": np.arange(100) ** 2}, index=np.arange(1000, 1100))
        self.y = pd.Series(np.tile([0, 0, 0, 1], 25), index=self.X.index)
        self.ids = pd.Series(np.arange(100), index=self.X.index)

    def test_folds_scaler_coverage_and_ensemble(self):
        RecordingScaler.fits = []
        model = Pipeline([("scaler", RecordingScaler()), ("lr", LogisticRegression())])
        result = avaliar_oof(self.X, self.y, {RL: model, RF: model}, self.ids)
        seen = []
        for fold in result["particoes"]:
            train, valid = fold["posicoes_treino"], fold["posicoes_validacao"]
            self.assertFalse(set(train) & set(valid))
            self.assertEqual(len(train) + len(valid), 100)
            self.assertEqual(fold["positivos_validacao"], 5)
            seen.extend(valid)
            for recorded, mean in RecordingScaler.fits[2*(fold["fold"]-1):2*fold["fold"]]:
                self.assertEqual(recorded, set(self.X.iloc[train].index))
                self.assertFalse(recorded & set(self.X.iloc[valid].index))
                np.testing.assert_allclose(mean, self.X.iloc[train].mean())
            np.testing.assert_allclose(result["oof"].iloc[valid][BASELINE], self.y.iloc[train].mean())
        self.assertEqual(sorted(seen), list(range(100)))
        self.assertEqual(len(RecordingScaler.fits), 10)
        np.testing.assert_allclose(result["oof"][ENSEMBLE], .9*result["oof"][RL]+.1*result["oof"][RF])
        self.assertFalse(result["oof"].isna().any().any())
        self.assertFalse(hasattr(model["scaler"], "mean_"))
        self.assertEqual(result["oof"].patient_id.tolist(), self.ids.tolist())

    def test_svm_inner_scaler_separation(self):
        RecordingScaler.fits = []
        with patch("src.modelo_svm.StandardScaler", RecordingScaler):
            svm = criar_modelo_svm()
            self.assertIsInstance(svm.estimator, Pipeline)
            self.assertEqual(svm.cv, 5)
            self.assertFalse(svm.ensemble)
            self.assertEqual(svm.estimator["svm"].random_state, 42)
            svm.fit(self.X, self.y)
        # Cinco ajustes internos de 80 registros e um reajuste final de 100.
        self.assertEqual(sorted(len(ids) for ids, _ in RecordingScaler.fits), [80]*5+[100])
        for ids, mean in RecordingScaler.fits:
            np.testing.assert_allclose(mean, self.X.loc[list(ids)].mean())
        internal = [ids for ids, _ in RecordingScaler.fits if len(ids) == 80]
        held_out = [set(self.X.index) - ids for ids in internal]
        self.assertEqual(set.union(*held_out), set(self.X.index))
        for i, ids in enumerate(held_out):
            for other in held_out[i+1:]:
                self.assertFalse(ids & other)

    def test_reject_misalignment(self):
        with self.assertRaises(ValueError):
            avaliar_oof(self.X, self.y.iloc[::-1], {RL: LogisticRegression(), RF: LogisticRegression()}, self.ids)


if __name__ == "__main__":
    unittest.main()
