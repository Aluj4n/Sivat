import logging
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.entities import Afirmacion, DecisionEditorial, EvaluacionIA, FuenteExterna
from services.clasificador_service import clasificar_senal
from services.verificacion_service import evaluar_y_guardar

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalizarRequest(BaseModel):
    texto: str = Field(..., min_length=10, max_length=5000, description="Afirmación o noticia a evaluar")


class DecisionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_periodista: str
    comentarios: Optional[str]
    fecha_decision: datetime


class EvaluacionResponse(BaseModel):
    afirmacion_id: int
    texto: str
    probabilidad_desinformacion: float
    # Lo que muestra el medidor: 100 - probabilidad de desinformación, en %.
    # Mide patrones de redacción, no verifica hechos (por eso siempre va con
    # recomendacion_sistema y nunca como "verdadero/falso", RNF-08).
    confianza_modelo: int
    senal: str
    recomendacion_sistema: str
    version_modelo: str
    fecha_evaluacion: Optional[datetime] = None
    # Origen cuando la afirmación vino del feed (trazabilidad, RNF-06)
    fuente_origen: Optional[str] = None
    url_original: Optional[str] = None
    # Desagregado de evidencia (Business Case 5.2) -- null hasta que exista el módulo RAG
    nivel_evidencia_disponible: Optional[str] = None
    fuentes_coincidentes: Optional[int] = None
    fuentes_contradictorias: Optional[int] = None
    fuente_oficial_encontrada: Optional[bool] = None
    cobertura_evidencia: Optional[str] = None
    decision: Optional[DecisionInfo] = None


class DecisionRequest(BaseModel):
    decision: Literal["Aceptado", "Rechazado", "Observado"]
    comentarios: Optional[str] = Field(None, max_length=1000)


def construir_respuesta(
    evaluacion: EvaluacionIA,
    texto: str,
    fuente: Optional[FuenteExterna] = None,
    decision: Optional[DecisionEditorial] = None,
) -> EvaluacionResponse:
    probabilidad = evaluacion.probabilidad_desinformacion
    return EvaluacionResponse(
        afirmacion_id=evaluacion.afirmacion_id,
        texto=texto,
        probabilidad_desinformacion=round(probabilidad, 4),
        confianza_modelo=round((1 - probabilidad) * 100),
        senal=clasificar_senal(probabilidad),
        recomendacion_sistema=evaluacion.recomendacion_sistema,
        version_modelo=evaluacion.version_modelo,
        fecha_evaluacion=evaluacion.fecha_evaluacion,
        fuente_origen=fuente.origen if fuente else None,
        url_original=fuente.url_original if fuente else None,
        nivel_evidencia_disponible=evaluacion.nivel_evidencia_disponible,
        fuentes_coincidentes=evaluacion.fuentes_coincidentes,
        fuentes_contradictorias=evaluacion.fuentes_contradictorias,
        fuente_oficial_encontrada=evaluacion.fuente_oficial_encontrada,
        cobertura_evidencia=evaluacion.cobertura_evidencia,
        decision=DecisionInfo.model_validate(decision) if decision else None,
    )


@router.post("/analyze", response_model=EvaluacionResponse)
async def analizar_afirmacion(payload: AnalizarRequest, db: AsyncSession = Depends(get_db)):
    """
    Ejecuta el clasificador sobre un texto ingresado a mano y persiste la
    Afirmacion + su EvaluacionIA. `recomendacion_sistema` siempre exige
    validación periodística, sin importar el resultado.
    """
    try:
        _, evaluacion = await evaluar_y_guardar(db, payload.texto)
    except RuntimeError as e:
        logger.error(f"Clasificador no disponible: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error al evaluar afirmación: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al evaluar la afirmación")

    await db.commit()
    await db.refresh(evaluacion)
    return construir_respuesta(evaluacion, payload.texto)


@router.get("/recientes", response_model=list[EvaluacionResponse])
async def listar_recientes(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """
    Alimenta el Dashboard y la vista Validación: últimas afirmaciones evaluadas,
    con su fuente de origen (si vinieron del feed) y la decisión editorial más
    reciente si ya existe (RF-09).
    """
    resultado = await db.execute(
        select(EvaluacionIA, Afirmacion.contenido, FuenteExterna)
        .join(Afirmacion, EvaluacionIA.afirmacion_id == Afirmacion.id)
        .outerjoin(FuenteExterna, Afirmacion.fuente_id == FuenteExterna.id)
        .order_by(EvaluacionIA.fecha_evaluacion.desc())
        .limit(limit)
    )
    filas = resultado.all()
    if not filas:
        return []

    ids_afirmacion = [ev.afirmacion_id for ev, _, _ in filas]
    decisiones_result = await db.execute(
        select(DecisionEditorial)
        .where(DecisionEditorial.afirmacion_id.in_(ids_afirmacion))
        .order_by(DecisionEditorial.fecha_decision.desc())
    )
    # Solo la decisión más reciente por afirmación (ya vienen ordenadas desc)
    decision_por_afirmacion: dict[int, DecisionEditorial] = {}
    for decision in decisiones_result.scalars().all():
        decision_por_afirmacion.setdefault(decision.afirmacion_id, decision)

    return [
        construir_respuesta(ev, contenido, fuente, decision_por_afirmacion.get(ev.afirmacion_id))
        for ev, contenido, fuente in filas
    ]


@router.post("/{afirmacion_id}/decision", response_model=DecisionInfo)
async def registrar_decision(afirmacion_id: int, payload: DecisionRequest, db: AsyncSession = Depends(get_db)):
    """
    Registra la decisión del periodista sobre una afirmación (RF-09/RF-11).
    La recomendación de la IA queda siempre diferenciada de esta decisión
    humana, tal como exige el control de supervisión del Business Case (5.1).
    """
    afirmacion = await db.get(Afirmacion, afirmacion_id)
    if afirmacion is None:
        raise HTTPException(status_code=404, detail="Afirmación no encontrada")

    ultima_evaluacion = await db.execute(
        select(EvaluacionIA)
        .where(EvaluacionIA.afirmacion_id == afirmacion_id)
        .order_by(EvaluacionIA.fecha_evaluacion.desc())
        .limit(1)
    )
    evaluacion = ultima_evaluacion.scalar_one_or_none()

    decision = DecisionEditorial(
        afirmacion_id=afirmacion_id,
        recomendacion_ia=clasificar_senal(evaluacion.probabilidad_desinformacion) if evaluacion else "Sin evaluación",
        decision_periodista=payload.decision,
        comentarios=payload.comentarios,
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)

    return DecisionInfo.model_validate(decision)
