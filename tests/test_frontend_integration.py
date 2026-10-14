import csv
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from api.main import create_app
from api.pacientes_demo import carregar_pacientes
from src.modelo_persistido import prever_probabilidade
from src.variables import VARIABLES_T0

ARTIFACT = ROOT / 'artifacts/rl_20261014T100407101829_b83773b9'


class TestFrontendIntegration(unittest.TestCase):
    def test_demo_contract_and_real_prediction(self):
        with TestClient(create_app(ARTIFACT)) as client:
            response = client.get('/demo/patients')
            self.assertEqual(response.status_code, 200)
            patients = response.json()
            self.assertEqual(len(patients), 30)
            self.assertEqual(len({p['patient_id'] for p in patients}), 30)
            expected = {'patient_id', 'data_avaliacao', *VARIABLES_T0}
            for p in patients:
                self.assertEqual(set(p), expected)
            inputs = {name: patients[0][name] for name in VARIABLES_T0}
            prediction = client.post('/predict', json=inputs)
            self.assertEqual(prediction.status_code, 200)
            self.assertEqual(prediction.json()['probabilidade'], prever_probabilidade(client.app.state.modelo, inputs))

    def test_static_files_and_no_internal_directories(self):
        with TestClient(create_app(ARTIFACT)) as client:
            for path in ['/frontend/', '/frontend/index.html', '/frontend/avaliacao.html', '/frontend/js/api.js', '/frontend/js/index.js', '/frontend/js/avaliacao.js', '/frontend/css/style.css']:
                self.assertEqual(client.get(path).status_code, 200, path)
            for path in ['/data/dataset.csv', '/artifacts/modelo.joblib', '/frontend/data/dataset.csv', '/frontend/../data/dataset.csv', '/frontend/%2e%2e/data/dataset.csv']:
                self.assertEqual(client.get(path).status_code, 404, path)

    def test_temporary_invalid_csv_and_controlled_error(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp)/'missing.csv'
            with self.assertRaises(FileNotFoundError): carregar_pacientes(missing)
            invalid = Path(temp)/'invalid.csv'
            invalid.write_text('patient_id,sepsis\nDEMO001,1\n', encoding='utf-8')
            with self.assertRaises(ValueError): carregar_pacientes(invalid)
            original = (ROOT/'data/dataset_interface.csv').read_text(encoding='utf-8')
            rows = list(csv.DictReader(io.StringIO(original)))
            for value in ['NaN', 'Infinity', '', 'text']:
                rows[0]['fc'] = value
                with invalid.open('w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
                with self.assertRaises(ValueError): carregar_pacientes(invalid)
            with patch('api.pacientes_demo.DEMO_CSV', missing), TestClient(create_app(ARTIFACT)) as client:
                with self.assertLogs('api.main', level='ERROR'): response = client.get('/demo/patients')
                self.assertEqual(response.status_code, 503)
                self.assertNotIn(str(missing), response.text)


if __name__ == '__main__': unittest.main()
