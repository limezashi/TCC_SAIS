"""Uvicorn: api.main:app. Configure TCC_MODEL_DIR explicitamente."""
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.modelo_persistido import carregar_modelo, prever_probabilidade, sha256
from .schemas import PredictRequest, PredictResponse, FINALIDADE

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

    return app


app = create_app()
