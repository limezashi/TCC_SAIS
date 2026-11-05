"""Uvicorn: api.main:app. Configure TCC_MODEL_DIR explicitamente."""
from contextlib import asynccontextmanager
from datetime import date
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.modelo_persistido import carregar_modelo, prever_probabilidade, sha256
from .schemas import (PredictRequest, PredictResponse, EvaluationResponse,
                      EvaluationHistoryItem, LatestEvaluationItem,
                      PaginatedPatientsResponse, FINALIDADE)
from .database import (paciente_existe, salvar_avaliacao, listar_avaliacoes,
                       listar_ultimas_avaliacoes, listar_pacientes_paginados)

LOGGER = logging.getLogger(__name__)


def create_app(pasta_artefato=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.modelo = None
        app.state.versao_modelo = None
        configured = pasta_artefato if pasta_artefato is not None else os.environ.get("TCC_MODEL_DIR")
        try:
            if not configured:
                raise ValueError("Defina TCC_MODEL_DIR com uma pasta de artefato confiavel.")
            folder = Path(configured).resolve()
            # Somente configuracao do operador; clientes nao escolhem arquivos.
            model = carregar_modelo(folder, origem_confiavel=True)
            version = sha256(folder / "modelo.joblib")
        except Exception as exc:
            LOGGER.exception("Falha no carregamento do modelo persistido")
            raise RuntimeError("Inicializacao interrompida: modelo indisponivel ou incompativel.") from exc
        app.state.modelo = model
        app.state.versao_modelo = version
        try:
            yield
        finally:
            app.state.modelo = None
            app.state.versao_modelo = None

    app = FastAPI(title="SAIS — demonstração acadêmica", version="1.0.0",
                  description=FINALIDADE, lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Nao reproduz input/ctx: NaN/Infinity nao sao serializaveis em JSON.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    def available(request):
        model = getattr(request.app.state, "modelo", None)
        version = getattr(request.app.state, "versao_modelo", None)
        if model is None or version is None:
            raise HTTPException(status_code=503, detail="Modelo indisponível.")
        return model, version

    @app.get("/health")
    def health(request: Request):
        _, version = available(request)
        return {"status": "ok", "versao_modelo": version}

    @app.post("/predict", response_model=PredictResponse)
    def predict(dados: PredictRequest, request: Request):
        model, version = available(request)
        try:
            probability = prever_probabilidade(model, dados.entradas_modelo())
            return PredictResponse(probabilidade=probability, versao_modelo=version)
        except Exception:
            LOGGER.exception("Falha na inferencia")
            raise HTTPException(status_code=500, detail="Falha ao calcular a probabilidade.") from None

    @app.get("/demo/patients", response_model=PaginatedPatientsResponse)
    def demo_patients(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=10, ge=1, le=100),
        search: str | None = Query(default=None, max_length=100),
        data_avaliacao: date | None = None,
    ):
        try:
            result = listar_pacientes_paginados(
                page=page,
                page_size=page_size,
                search=search.strip() if search and search.strip() else None,
                data_avaliacao=data_avaliacao,
            )
            result["total_pages"] = (result["total"] + page_size - 1) // page_size
            return result
        except Exception:
            LOGGER.exception("Falha ao carregar pacientes")
            raise HTTPException(status_code=503, detail="Pacientes indisponiveis.") from None

    def require_patient(patient_id):
        try:
            exists = paciente_existe(patient_id)
        except Exception:
            LOGGER.exception("Falha ao consultar paciente")
            raise HTTPException(status_code=503, detail="Banco de dados indisponivel.") from None
        if not exists:
            raise HTTPException(status_code=404, detail="Paciente nao encontrado.")

    @app.post("/patients/{patient_id}/evaluations", response_model=EvaluationResponse, status_code=201)
    def evaluate_patient(patient_id: str, dados: PredictRequest, request: Request):
        require_patient(patient_id)
        model, version = available(request)
        entradas = dados.entradas_modelo()
        try:
            probability = prever_probabilidade(model, entradas)
        except Exception:
            LOGGER.exception("Falha na inferencia")
            raise HTTPException(status_code=500, detail="Falha ao calcular a probabilidade.") from None
        try:
            saved = salvar_avaliacao(patient_id, probability, version, entradas)
        except Exception:
            LOGGER.exception("Falha ao registrar avaliacao")
            raise HTTPException(status_code=503, detail="Nao foi possivel registrar a avaliacao.") from None
        return EvaluationResponse(id=saved["id"], patient_id=patient_id,
                                  probabilidade=probability, versao_modelo=version,
                                  calculado_em=saved["calculado_em"])

    @app.get("/patients/{patient_id}/evaluations", response_model=list[EvaluationHistoryItem])
    def evaluation_history(patient_id: str):
        require_patient(patient_id)
        try:
            return listar_avaliacoes(patient_id)
        except Exception:
            LOGGER.exception("Falha ao consultar historico")
            raise HTTPException(status_code=503, detail="Banco de dados indisponivel.") from None

    @app.get("/patients/{patient_id}/evaluations/latest", response_model=EvaluationHistoryItem)
    def latest_evaluation(patient_id: str):
        require_patient(patient_id)
        try:
            rows = listar_avaliacoes(patient_id, limite=1)
        except Exception:
            LOGGER.exception("Falha ao consultar ultima avaliacao")
            raise HTTPException(status_code=503, detail="Banco de dados indisponivel.") from None
        if not rows:
            raise HTTPException(status_code=404, detail="Paciente ainda nao possui avaliacoes.")
        return rows[0]

    @app.get("/evaluations/latest", response_model=list[LatestEvaluationItem])
    def latest_evaluations():
        try:
            return listar_ultimas_avaliacoes()
        except Exception:
            LOGGER.exception("Falha ao consultar ultimas avaliacoes")
            raise HTTPException(status_code=503, detail="Banco de dados indisponivel.") from None

    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(frontend_dir / "index.html")

    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app


app = create_app()
