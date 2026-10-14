"""Leitura exclusiva do CSV demonstrativo, sem alvo e sem inferencia."""
import csv
from datetime import date
from pathlib import Path
from .schemas import PredictRequest
from src.variables import VARIABLES_T0

DEMO_CSV = Path(__file__).resolve().parents[1] / "data/dataset_interface.csv"


def carregar_pacientes(caminho=None):
    with Path(caminho or DEMO_CSV).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        expected = {"patient_id", "data_avaliacao", *VARIABLES_T0}
        if not reader.fieldnames or len(reader.fieldnames) != len(expected) or set(reader.fieldnames) != expected:
            raise ValueError("Estrutura do CSV demonstrativo invalida.")
        patients, ids = [], set()
        for row in reader:
            if None in row or any(v is None or not v.strip() for v in row.values()):
                raise ValueError("Registro incompleto.")
            identifier = row["patient_id"].strip()
            if not identifier.startswith("DEMO") or identifier in ids:
                raise ValueError("Identificador demonstrativo invalido ou duplicado.")
            day = date.fromisoformat(row["data_avaliacao"])
            inputs = PredictRequest(**{name: float(row[name]) for name in VARIABLES_T0})
            patients.append({"patient_id": identifier, "data_avaliacao": day.isoformat(), **inputs.entradas_modelo()})
            ids.add(identifier)
        if len(patients) != 30:
            raise ValueError("Esperados 30 pacientes demonstrativos.")
        return patients
