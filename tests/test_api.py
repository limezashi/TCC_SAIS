import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from api.main import create_app
from api.schemas import PredictRequest
from src.modelo_persistido import carregar_modelo, prever_probabilidade, sha256
from src.variables import VARIABLES_T0

ARTIFACT = ROOT / "artifacts/rl_20261014T100407101829_b83773b9"
PAYLOAD = {"pas": 127.6, "fc": 108.1, "temperatura": 36.08, "leucocitos": 10.4,
           "neutrofilos": 9.82, "rnl": 5.34, "bastonetes": 5.35, "pao2_fio2": 223,
           "creatinina": 1.3, "lactato": 3.15, "plaquetas": 193}


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes = {p: sha256(p) for p in ARTIFACT.iterdir() if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        for path, digest in cls.hashes.items():
            if sha256(path) != digest:
                raise AssertionError("Artefato real alterado pelos testes")

    def test_dynamic_prediction_health_and_single_load(self):
        with patch("api.main.carregar_modelo", wraps=carregar_modelo) as load, \
             patch("sklearn.linear_model.LogisticRegression.fit", side_effect=AssertionError("Treinamento proibido")):
            with TestClient(create_app(ARTIFACT)) as client:
                health = client.get('/health')
                self.assertEqual(health.status_code, 200)
                version = sha256(ARTIFACT/'modelo.joblib')
                self.assertEqual(health.json()['versao_modelo'], version)
                first = client.post('/predict', json=PAYLOAD)
                second_payload = {**PAYLOAD, 'lactato': .4}
                second = client.post('/predict', json=second_payload)
                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 200)
                self.assertNotEqual(first.json()['probabilidade'], second.json()['probabilidade'])
                for payload, response in [(PAYLOAD, first), (second_payload, second)]:
                    p = response.json()['probabilidade']
                    self.assertTrue(0 <= p <= 1)
                    self.assertEqual(p, prever_probabilidade(client.app.state.modelo, payload))
                    self.assertEqual(response.json()['versao_modelo'], version)
                    self.assertEqual(set(response.json()), {'probabilidade', 'versao_modelo', 'finalidade'})
                reversed_response = client.post('/predict', json=dict(reversed(list(PAYLOAD.items()))))
                self.assertEqual(reversed_response.json(), first.json())
                load.assert_called_once_with(ARTIFACT.resolve(), origem_confiavel=True)
            self.assertIsNone(client.app.state.modelo)

    def test_strict_validation_all_fields_and_json_errors(self):
        with TestClient(create_app(ARTIFACT)) as client:
            for key in VARIABLES_T0:
                for value in ['100', True, False, None]:
                    with self.subTest(field=key, value=value):
                        self.assertEqual(client.post('/predict', json={**PAYLOAD, key:value}).status_code, 422)
                missing = {k:v for k,v in PAYLOAD.items() if k != key}
                self.assertEqual(client.post('/predict', json=missing).status_code, 422)
                for raw in ['NaN', 'Infinity', '-Infinity', '1e999']:
                    text = json.dumps({**PAYLOAD, key:None}).replace('null', raw)
                    self.assertEqual(client.post('/predict', content=text, headers={'Content-Type':'application/json'}).status_code, 422)
            self.assertEqual(client.post('/predict', json={**PAYLOAD, 'extra':1}).status_code, 422)
            self.assertEqual(client.post('/predict', json=[]).status_code, 422)
            self.assertEqual(client.post('/predict', content='{', headers={'Content-Type':'application/json'}).status_code, 422)
        self.assertEqual(list(PredictRequest(**PAYLOAD).entradas_modelo()), VARIABLES_T0)

    def test_unavailability_and_controlled_inference_failure(self):
        with TestClient(create_app(ARTIFACT)) as client:
            with patch('api.main.prever_probabilidade', side_effect=RuntimeError('private path')):
                with self.assertLogs('api.main', level='ERROR'):
                    response = client.post('/predict', json=PAYLOAD)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn('private path', response.text)
            client.app.state.modelo = None
            self.assertEqual(client.get('/health').status_code, 503)
            self.assertEqual(client.post('/predict', json=PAYLOAD).status_code, 503)

    def test_configuration_required(self):
        with patch.dict(os.environ, {}, clear=True), self.assertLogs('api.main', level='ERROR'):
            with self.assertRaises(RuntimeError):
                with TestClient(create_app()): pass

    def test_startup_failures_on_temporary_artifacts(self):
        with tempfile.TemporaryDirectory() as temp, patch('src.modelo_persistido.ARTIFACT_ROOT', Path(temp)):
            folder = Path(temp)/'rl_copy'
            shutil.copytree(ARTIFACT, folder)
            metadata = folder/'metadados.json'
            original = metadata.read_bytes()
            values = json.loads(original)
            values['python'] = '0.0.0'
            metadata.write_text(json.dumps(values), encoding='utf-8')
            with self.assertLogs('api.main', level='ERROR'), self.assertRaises(RuntimeError):
                with TestClient(create_app(folder)): pass
            metadata.write_bytes(original)
            with (folder/'modelo.joblib').open('ab') as f: f.write(b'corrupt')
            with self.assertLogs('api.main', level='ERROR'), self.assertRaises(RuntimeError):
                with TestClient(create_app(folder)): pass
            with self.assertLogs('api.main', level='ERROR'), self.assertRaises(RuntimeError):
                with TestClient(create_app(Path(temp)/'missing')): pass


if __name__ == '__main__':
    unittest.main()
