import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.modelo_rl import criar_modelo_rl
from src.preparacao_dados import preparar_dados
from src.variables import VARIABLES_T0
from src.modelo_persistido import salvar_modelo, carregar_modelo, prever_probabilidade, hash_identificadores


class TestPersistencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = ROOT / "data/dataset.csv"
        cls.X, _, cls.y, _ = preparar_dados(str(cls.dataset))
        cls.ids = pd.read_csv(cls.dataset, usecols=["patient_id"]).loc[cls.X.index, "patient_id"]
        cls.model = criar_modelo_rl().fit(cls.X, cls.y)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch("src.modelo_persistido.ARTIFACT_ROOT", self.root)
        patcher.start(); self.addCleanup(patcher.stop)
        self.folder = self.root / "rl_test"
        salvar_modelo(self.model, self.folder, self.dataset, self.ids, int(self.y.sum()))
        self.data = self.X.iloc[0].to_dict()

    def test_roundtrip_all_training_and_order(self):
        model = carregar_modelo(self.folder, origem_confiavel=True)
        np.testing.assert_array_equal(self.model.predict_proba(self.X), model.predict_proba(self.X))
        self.assertEqual(list(model.feature_names_in_), VARIABLES_T0)
        self.assertEqual(prever_probabilidade(model, self.data), prever_probabilidade(model, dict(reversed(list(self.data.items())))))
        self.assertTrue(0 <= prever_probabilidade(model, self.data) <= 1)
        metadata = json.loads((self.folder/'metadados.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['training']['ids_sha256'], hash_identificadores(self.ids))

    def test_invalid_inputs(self):
        cases = [{}, {**self.data, 'unknown': 1}]
        cases += [{**self.data, 'fc': v} for v in [None, True, np.bool_(False), '100', float('nan'), float('inf'), -float('inf')]]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                prever_probabilidade(self.model, data)

    def test_trust_and_integrity_before_deserialization(self):
        with patch('src.modelo_persistido.joblib.load') as load:
            with self.assertRaises(ValueError): carregar_modelo(self.folder)
            with (self.folder/'modelo.joblib').open('ab') as f: f.write(b'corrupt')
            with self.assertRaises(ValueError): carregar_modelo(self.folder, origem_confiavel=True)
            load.assert_not_called()

    def test_incompatible_metadata_before_deserialization(self):
        path = self.folder/'metadados.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        for key, value in [('features', list(reversed(VARIABLES_T0))), ('producer', 'external'), ('packages', {}), ('configuration', {})]:
            with self.subTest(key=key):
                path.write_text(json.dumps({**original, key: value}), encoding='utf-8')
                with patch('src.modelo_persistido.joblib.load') as load:
                    with self.assertRaises(ValueError): carregar_modelo(self.folder, origem_confiavel=True)
                    load.assert_not_called()

    def test_no_overwrite_or_external_directory(self):
        with self.assertRaises(FileExistsError):
            salvar_modelo(self.model, self.folder, self.dataset, self.ids, int(self.y.sum()))
        with self.assertRaises(ValueError):
            carregar_modelo(self.root.parent, origem_confiavel=True)


if __name__ == '__main__':
    unittest.main()
