import logging
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.entities import Afirmacion, DecisionEditorial, EvaluacionIA
from services.clasificador_service import (
    VERSION_MODELO,
    clasificar_senal,
    predecir_probabilidad,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalizarRequest(BaseModel):
    texto: str = Field(..., min_length=10, max_length=5000, description="Afirmación o noticia a evaluar")


class EvaluacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    afirmacion_id: int
    texto: str
    probabilidad_desinformacion: float
    senal: str
    recomendacion_sistema: str
    version_modelo: str
    # Desagregado de evidencia (Business Case 5.2) -- null hasta que exista el módulo RAG
    nivel_evidencia_disponible: Optional[str]
    fuentes_coincidentes: Optional[int]
    fuentes_contradictorias: Optional[int]
    fuente_oficial_encontrada: Optional[bool]
    cobertura_evidencia: Optional[str]


class DecisionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_periodista: str
    comentarios: Optional[str]
    fecha_decision: datetime


class EvaluacionConDecision(EvaluacionResponse):
    fecha_evaluacion: datetime
    decision: Optional[DecisionInfo] = None


class DecisionRequest(BaseModel):
    decision: Literal["Aceptado", "Rechazado", "Observado"]
    comentarios: Optional[str] = Field(None, max_length=1000)


@router.post("/analyze", response_model=EvaluacionResponse)
async def analizar_afirmacion(payload: AnalizarRequest, db: AsyncSession = Depends(get_db)):
    """
    Ejecuta el clasificador de señal de desinformación sobre un texto y
    persiste la Afirmacion + su EvaluacionIA.

    RESTRICCIÓN ÉTICA: la respuesta nunca es "verdadero/falso" (RNF-08).
    `recomendacion_sistema` siempre exige validación periodística,
    independientemente de la probabilidad calculada.
    """
    try:
        probabilidad = predecir_probabilidad(payload.texto)
    except RuntimeError as e:
        logger.error(f"Clasificador no disponible: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error al evaluar afirmación: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al evaluar la afirmación")

    afirmacion = Afirmacion(contenido=payload.texto)
    db.add(afirmacion)
    await db.flush()  # asigna afirmacion.id sin cerrar la transacción

    evaluacion = EvaluacionIA(
        afirmacion_id=afirmacion.id,
        probabilidad_desinformacion=probabilidad,
        version_modelo=VERSION_MODELO,
        recomendacion_sistema="Requiere validación periodística",
    )
    db.add(evaluacion)
    await db.commit()
    await db.refresh(evaluacion)

    return EvaluacionResponse(
        afirmacion_id=afirmacion.id,
        texto=payload.texto,
        probabilidad_desinformacion=round(probabilidad, 4),
        senal=clasificar_senal(probabilidad),
        recomendacion_sistema=evaluacion.recomendacion_sistema,
        version_modelo=evaluacion.version_modelo,
        nivel_evidencia_disponible=evaluacion.nivel_evidencia_disponible,
        fuentes_coincidentes=evaluacion.fuentes_coincidentes,
        fuentes_contradictorias=evaluacion.fuentes_contradictorias,
        fuente_oficial_encontrada=evaluacion.fuente_oficial_encontrada,
        cobertura_evidencia=evaluacion.cobertura_evidencia,
    )


@router.get("/recientes", response_model=list[EvaluacionConDecision])
async def listar_recientes(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """
    Alimenta el Dashboard y la vista Validación: últimas afirmaciones evaluadas
    por el clasificador, con la decisión editorial más reciente si ya existe
    (RF-09). No filtra por estado -- el frontend decide cómo agrupar
    pendientes vs. ya validadas.
    """
    resultado = await db.execute(
        select(EvaluacionIA, Afirmacion.contenido)
        .join(Afirmacion, EvaluacionIA.afirmacion_id == Afirmacion.id)
        .order_by(EvaluacionIA.fecha_evaluacion.desc())
        .limit(limit)
    )
    filas = resultado.all()
    if not filas:
        return []

    ids_afirmacion = [ev.afirmacion_id for ev, _ in filas]
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
        EvaluacionConDecision(
            afirmacion_id=ev.afirmacion_id,
            texto=contenido,
            probabilidad_desinformacion=round(ev.probabilidad_desinformacion, 4),
            senal=clasificar_senal(ev.probabilidad_desinformacion),
            recomendacion_sistema=ev.recomendacion_sistema,
            version_modelo=ev.version_modelo,
            nivel_evidencia_disponible=ev.nivel_evidencia_disponible,
            fuentes_coincidentes=ev.fuentes_coincidentes,
            fuentes_contradictorias=ev.fuentes_contradictorias,
            fuente_oficial_encontrada=ev.fuente_oficial_encontrada,
            cobertura_evidencia=ev.cobertura_evidencia,
            fecha_evaluacion=ev.fecha_evaluacion,
            decision=(
                DecisionInfo.model_validate(decision_por_afirmacion[ev.afirmacion_id])
                if ev.afirmacion_id in decision_por_afirmacion
                else None
            ),
        )
        for ev, contenido in filas
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
