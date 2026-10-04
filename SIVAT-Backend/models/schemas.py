from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class FuenteExternaBase(BaseModel):
    origen: str
    identificador_externo: str
    texto_procesado: str
    metadatos: Optional[str] = None

class FuenteExternaCreate(FuenteExternaBase):
    pass

class FuenteExternaResponse(FuenteExternaBase):
    id: int
    fecha_recoleccion: datetime

    model_config = ConfigDict(from_attributes=True)


class TendenciaBase(BaseModel):
    tema: str
    volumen_menciones: int
    velocidad_crecimiento: float

class TendenciaCreate(TendenciaBase):
    pass

class TendenciaResponse(TendenciaBase):
    id: int
    fecha_registro: datetime

    model_config = ConfigDict(from_attributes=True)
