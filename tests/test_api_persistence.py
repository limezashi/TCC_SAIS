import unittest
import os
import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api import main
from api.database import obter_conexao, listar_ultimas_avaliacoes, listar_pacientes_paginados
from src.variables import VARIABLES_T0


class ApiPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.dict(os.environ, {"TCC_MODEL_DIR": str(Path("artifacts/rl_20261014T100407101829_b83773b9").resolve())}),
            patch.object(main, "carregar_modelo", return_value=object()),
            patch.object(main, "sha256", return_value="a" * 64),
            patch.object(main, "prever_probabilidade", return_value=0.25),
        ]
        for item in self.patches:
            item.start()
        self.app = main.create_app()
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        self.app.state.modelo = object()
        self.app.state.versao_modelo = "a" * 64
        self.payload = {name: float(index + 1) for index, name in enumerate(VARIABLES_T0)}

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()

    def test_predict_contract_still_works_and_rejects_extra_fields(self):
        response = self.client.post("/predict", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["probabilidade"], 0.25)
        self.assertEqual(self.client.post("/predict", json={**self.payload, "extra": 1}).status_code, 422)
        invalid = {**self.payload, "pas": float("nan")}
        self.assertEqual(self.client.post("/predict", content=json.dumps(invalid), headers={"Content-Type": "application/json"}).status_code, 422)

    @patch.object(main, "listar_pacientes_paginados")
    def test_patient_page_contract_filters_and_page_metadata(self, listing):
        patient = {
            "patient_id": "P001", "data_avaliacao": date(2026, 10, 20),
            **self.payload, "ultima_avaliacao": {
                "id": 4, "probabilidade": 0.4, "modelo_hash": "c" * 64,
                "calculado_em": "2026-10-21T10:00:00+00:00",
            },
        }
        listing.return_value = {"items": [patient], "total": 21, "page": 2, "page_size": 10}
        response = self.client.get(
            "/demo/patients?page=2&page_size=10&search=P00&data_avaliacao=2026-10-20"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_pages"], 3)
        self.assertEqual(response.json()["items"][0]["ultima_avaliacao"]["id"], 4)
        listing.assert_called_once_with(
            page=2, page_size=10, search="P00", data_avaliacao=date(2026, 10, 20)
        )

    @patch.object(main, "listar_pacientes_paginados")
    def test_invalid_page_size_date_and_search_are_rejected(self, listing):
        for query in (
            "page=0", "page_size=101", "data_avaliacao=not-a-date", "search=" + "x" * 101
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/demo/patients?" + query).status_code, 422)
        listing.assert_not_called()

    @patch.object(main, "listar_pacientes_paginados", return_value={
        "items": [], "total": 0, "page": 1, "page_size": 10
    })
    def test_no_matching_patients_returns_zero_pages(self, listing):
        response = self.client.get("/demo/patients?search=missing")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "items": [], "total": 0, "page": 1, "page_size": 10, "total_pages": 0
        })

    @patch.object(main, "listar_pacientes_paginados", return_value={
        "items": [], "total": 23, "page": 5, "page_size": 10
    })
    def test_page_beyond_last_page_returns_no_items_but_keeps_total(self, listing):
        response = self.client.get("/demo/patients?page=5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "items": [], "total": 23, "page": 5, "page_size": 10, "total_pages": 3
        })

    @patch.object(main, "paciente_existe", return_value=True)
    @patch.object(main, "salvar_avaliacao", return_value={"id": 41, "calculado_em": "2026-11-05T12:00:00+00:00"})
    def test_evaluation_persists_model_probability_and_all_inputs(self, save, exists):
        response = self.client.post("/patients/DEMO001/evaluations", json=self.payload)
        self.assertEqual(response.status_code, 201)
        result = response.json()
        self.assertEqual((result["id"], result["patient_id"], result["probabilidade"]), (41, "DEMO001", 0.25))
        self.assertEqual(result["versao_modelo"], "a" * 64)
        args = save.call_args.args
        self.assertEqual(args[0:3], ("DEMO001", 0.25, "a" * 64))
        self.assertEqual(args[3], self.payload)
        self.assertEqual(len(args[3]), 11)

    @patch.object(main, "paciente_existe", return_value=True)
    @patch.object(main, "salvar_avaliacao", side_effect=[
        {"id": 51, "calculado_em": "2026-11-05T12:00:00+00:00"},
        {"id": 52, "calculado_em": "2026-11-05T12:01:00+00:00"},
    ])
    def test_repeated_evaluations_create_distinct_records(self, save, exists):
        first = self.client.post("/patients/DEMO001/evaluations", json=self.payload)
        second = self.client.post("/patients/DEMO001/evaluations", json=self.payload)
        self.assertEqual((first.json()["id"], second.json()["id"]), (51, 52))
        self.assertEqual(save.call_count, 2)

    @patch.object(main, "paciente_existe", return_value=False)
    @patch.object(main, "salvar_avaliacao")
    def test_unknown_patient_is_rejected_without_write(self, save, exists):
        response = self.client.post("/patients/UNKNOWN/evaluations", json=self.payload)
        self.assertEqual(response.status_code, 404)
        save.assert_not_called()

    @patch.object(main, "paciente_existe", return_value=True)
    @patch.object(main, "salvar_avaliacao", side_effect=RuntimeError("database unavailable"))
    def test_database_write_failure_is_not_reported_as_saved(self, save, exists):
        response = self.client.post("/patients/DEMO001/evaluations", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("id", response.json())

    @patch.object(main, "paciente_existe", return_value=True)
    @patch.object(main, "listar_avaliacoes", return_value=[])
    def test_empty_history_and_latest(self, listing, exists):
        self.assertEqual(self.client.get("/patients/DEMO001/evaluations").json(), [])
        self.assertEqual(self.client.get("/patients/DEMO001/evaluations/latest").status_code, 404)

    @patch.object(main, "paciente_existe", return_value=True)
    @patch.object(main, "listar_avaliacoes")
    def test_history_is_returned_for_requested_patient(self, listing, exists):
        rows = [{"id": 2, "probabilidade": 0.5, "modelo_hash": "b" * 64,
                 "calculado_em": "2026-11-05T12:00:00+00:00", "entradas_utilizadas": self.payload},
                {"id": 1, "probabilidade": 0.25, "modelo_hash": "a" * 64,
                 "calculado_em": "2026-11-04T12:00:00+00:00", "entradas_utilizadas": self.payload}]
        listing.return_value = rows
        response = self.client.get("/patients/DEMO001/evaluations")
        self.assertEqual([row["id"] for row in response.json()], [2, 1])
        listing.assert_called_once_with("DEMO001")

    @patch.object(main, "listar_ultimas_avaliacoes", return_value=[
        {"patient_id": "DEMO001", "id": 52, "probabilidade": 0.25,
         "modelo_hash": "a" * 64, "calculado_em": "2026-11-05T12:01:00+00:00"}
    ])
    def test_consolidated_latest_endpoint_returns_only_patients_with_evaluations(self, listing):
        response = self.client.get("/evaluations/latest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            "patient_id": "DEMO001", "id": 52, "probabilidade": 0.25,
            "modelo_hash": "a" * 64, "calculado_em": "2026-11-05T12:01:00+00:00"
        }])
        listing.assert_called_once_with()

    @patch.object(main, "listar_ultimas_avaliacoes", return_value=[])
    def test_consolidated_latest_endpoint_returns_empty_list_without_evaluations(self, listing):
        response = self.client.get("/evaluations/latest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch.object(main, "paciente_existe", return_value=True)
    @patch.object(main, "prever_probabilidade", side_effect=RuntimeError("inference failed"))
    @patch.object(main, "salvar_avaliacao")
    def test_inference_failure_does_not_write(self, save, predict, exists):
        response = self.client.post("/patients/DEMO001/evaluations", json=self.payload)
        self.assertEqual(response.status_code, 500)
        save.assert_not_called()


class ReadOnlyPostgresIntegrationTests(unittest.TestCase):
    @patch("api.database.obter_conexao")
    def test_paginated_query_binds_filters_and_limits_latest_lookup_to_page(self, connect):
        calculated = datetime.fromisoformat("2026-10-20T12:00:00+00:00")
        clinical_date = date(2026, 10, 20)
        connection = connect.return_value
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = (21,)
        cursor.fetchall.return_value = [
            ("P001", clinical_date, *([1.0] * 11), 8, 0.75, "a" * 64, calculated),
            ("P002", clinical_date, *([2.0] * 11), None, None, None, None),
        ]

        result = listar_pacientes_paginados(
            page=2, page_size=10, search="P00", data_avaliacao=clinical_date
        )

        count_query, count_params = cursor.execute.call_args_list[0].args
        page_query, page_params = cursor.execute.call_args_list[1].args
        self.assertIn("strpos(lower(patient_id), lower(%s))", count_query)
        self.assertIn("data_avaliacao = %s", count_query)
        self.assertEqual(count_params, ["P00", clinical_date])
        self.assertEqual(page_params, ["P00", clinical_date, 10, 10])
        self.assertNotIn("LIKE 'DEMO%'", page_query)
        self.assertIn("ORDER BY patient_id\n            LIMIT %s OFFSET %s", page_query)
        self.assertIn("LEFT JOIN LATERAL", page_query)
        self.assertIn("ORDER BY calculado_em DESC, id DESC", page_query)
        self.assertLess(page_query.index("LIMIT %s OFFSET %s"), page_query.index("LEFT JOIN LATERAL"))
        self.assertEqual(result["total"], 21)
        self.assertEqual(result["items"][0]["ultima_avaliacao"]["id"], 8)
        self.assertIsNone(result["items"][1]["ultima_avaliacao"])

    @patch("api.database.obter_conexao")
    def test_last_page_can_contain_only_remaining_rows(self, connect):
        connection = connect.return_value
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = (23,)
        base = (date(2026, 10, 20), *([1.0] * 11), None, None, None, None)
        cursor.fetchall.return_value = [(f"P{n:03}", *base) for n in (21, 22, 23)]

        result = listar_pacientes_paginados(page=3, page_size=10)

        self.assertEqual(result["total"], 23)
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(cursor.execute.call_args.args[1], [10, 20])

    @patch("api.database.obter_conexao")
    def test_latest_query_uses_distinct_on_and_tiebreaker(self, connect):
        timestamp = datetime.fromisoformat("2026-11-05T12:00:00+00:00")
        connection = connect.return_value
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value
        cursor.__enter__.return_value = cursor
        cursor.fetchall.return_value = [("DEMO001", 9, 0.3, "f" * 64, timestamp)]

        rows = listar_ultimas_avaliacoes()

        query = cursor.execute.call_args.args[0]
        self.assertIn("DISTINCT ON (patient_id)", query)
        self.assertIn("ORDER BY patient_id, calculado_em DESC, id DESC", query)
        self.assertEqual(rows[0]["patient_id"], "DEMO001")
        self.assertEqual(rows[0]["id"], 9)

    def test_database_connection_and_thirty_demo_patients(self):
        try:
            with obter_conexao() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM pacientes WHERE patient_id LIKE 'DEMO%';")
                    count = cursor.fetchone()[0]
        except Exception as exc:
            self.skipTest(f"PostgreSQL indisponivel ou nao configurado ({type(exc).__name__}).")
        self.assertEqual(count, 30)

    def test_real_postgres_pages_and_filters_use_existing_demo_rows(self):
        try:
            first = listar_pacientes_paginados(page=1, page_size=10)
            second = listar_pacientes_paginados(page=2, page_size=10)
            last = listar_pacientes_paginados(page=3, page_size=10)
        except Exception as exc:
            self.skipTest(f"PostgreSQL indisponivel ou nao configurado ({type(exc).__name__}).")
        self.assertEqual((first["total"], second["total"], last["total"]), (30, 30, 30))
        self.assertEqual((len(first["items"]), len(second["items"]), len(last["items"])), (10, 10, 10))
        identifiers = [row["patient_id"] for page in (first, second, last) for row in page["items"]]
        self.assertEqual(identifiers, sorted(identifiers))
        self.assertEqual(len(set(identifiers)), 30)

        matched = listar_pacientes_paginados(search="DEMO02", page_size=100)
        self.assertTrue(all("demo02" in row["patient_id"].lower() for row in matched["items"]))
        chosen_date = first["items"][0]["data_avaliacao"]
        by_date = listar_pacientes_paginados(data_avaliacao=chosen_date, page_size=100)
        self.assertTrue(all(row["data_avaliacao"] == chosen_date for row in by_date["items"]))
        combined = listar_pacientes_paginados(
            search=first["items"][0]["patient_id"], data_avaliacao=chosen_date, page_size=100
        )
        self.assertEqual([row["patient_id"] for row in combined["items"]], [first["items"][0]["patient_id"]])

    def test_paginated_http_contract_against_postgres(self):
        with patch.dict(os.environ, {"TCC_MODEL_DIR": str(Path("artifacts/rl_20261014T100407101829_b83773b9").resolve())}), \
             patch.object(main, "carregar_modelo", return_value=object()), \
             patch.object(main, "sha256", return_value="a" * 64):
            try:
                with TestClient(main.create_app()) as client:
                    response = client.get("/demo/patients?page=1&page_size=10")
            except Exception as exc:
                self.skipTest(f"PostgreSQL indisponivel ou nao configurado ({type(exc).__name__}).")
        if response.status_code == 503:
            self.skipTest("PostgreSQL indisponivel ou nao configurado.")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual((payload["total"], payload["page"], payload["page_size"], payload["total_pages"]), (30, 1, 10, 3))
        self.assertEqual(len(payload["items"]), 10)
        self.assertIn("ultima_avaliacao", payload["items"][0])


if __name__ == "__main__":
    unittest.main()
