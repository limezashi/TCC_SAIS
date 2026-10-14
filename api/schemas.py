"""Contrato HTTP; validacao do modelo continua em src.modelo_persistido."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from src.variables import VARIABLES_T0

NumeroFinito = Annotated[float, Field(strict=True, allow_inf_nan=False)]
FINALIDADE = "Demonstração acadêmica com dados sintéticos; sem validação clínica."


class PredictRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    pas: NumeroFinito
    fc: NumeroFinito
    temperatura: NumeroFinito
    leucocitos: NumeroFinito
    neutrofilos: NumeroFinito
    rnl: NumeroFinito
    bastonetes: NumeroFinito
    pao2_fio2: NumeroFinito
    creatinina: NumeroFinito
    lactato: NumeroFinito
    plaquetas: NumeroFinito

    def entradas_modelo(self):
        dados = self.model_dump()
        return {nome: dados[nome] for nome in VARIABLES_T0}


class PredictResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    probabilidade: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    versao_modelo: str
    finalidade: str = FINALIDADE


if set(PredictRequest.model_fields) != set(VARIABLES_T0):
    raise RuntimeError("Contrato HTTP diferente das variaveis do modelo.")
