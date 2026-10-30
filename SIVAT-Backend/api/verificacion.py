import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import List, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.eventbus import feed_bus
from db.session import get_db
from models.entities import (
    Afirmacion, DecisionEditorial, EvaluacionIA, EvidenciaAfirmacion, FuenteExterna, NoticiaFeed,
)
from services.clasificador_service import clasificar_senal
from services.contenido_service import Contenido, es_url, obtener_contenido
from services.evidencia_service import buscar_y_guardar_evidencia, explicar, titular_de
from services.normalizacion import _identificador, _recortar, serializar_feed
from services.verificacion_service import CONCLUSIONES, DECISIONES, evaluar_y_guardar

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalizarRequest(BaseModel):
    texto: str = Field(
        ..., min_length=10, max_length=20000,
        description="Afirmación o noticia a evaluar, o el enlace a la noticia (se descarga su contenido)",
    )


class DecisionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_periodista: str
    conclusion: Optional[str] = None
    comentarios: Optional[str]
    fecha_decision: datetime


class EvidenciaInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tipo: str  # 'verificacion' | 'medio'
    origen: Optional[str]
    titulo: Optional[str]
    url: Optional[str]
    # Calificación del verificador (atribuida a él), nunca de SIVAT
    calificacion: Optional[str]
    similitud: float
    fecha_publicacion: Optional[datetime]


class EvaluacionResponse(BaseModel):
    afirmacion_id: int
    texto: str
    probabilidad_desinformacion: float
    # Lo que muestra el medidor: 100 - probabilidad de desinformación, en %.
    # Mide patrones de redacción, no verifica hechos (por eso siempre va con
    # recomendacion_sistema y nunca como "verdadero/falso", RNF-08).
    # Null si el texto es muy corto para el modelo (texto_suficiente=False).
    confianza_modelo: Optional[int]
    texto_suficiente: bool
    palabras_analizadas: int
    senal: str
    recomendacion_sistema: str
    version_modelo: str
    fecha_evaluacion: Optional[datetime] = None
    # Origen cuando la afirmación vino del feed (trazabilidad, RNF-06)
    fuente_origen: Optional[str] = None
    url_original: Optional[str] = None
    # Desagregado de evidencia (Business Case 5.2, módulo RAG). Null si la
    # evidencia no se buscó (evaluaciones previas al módulo o búsqueda fallida).
    evidencia_buscada: bool = False
    nivel_evidencia_disponible: Optional[str] = None
    fuentes_coincidentes: Optional[int] = None
    fuentes_contradictorias: Optional[int] = None
    fuente_oficial_encontrada: Optional[bool] = None
    cobertura_evidencia: Optional[str] = None
    # El "por qué" bajo el medidor: razones generadas por reglas, sin veredicto
    explicacion: List[str] = []
    evidencias: List[EvidenciaInfo] = []
    decision: Optional[DecisionInfo] = None


class DecisionRequest(BaseModel):
    decision: Literal[DECISIONES]
    conclusion: Optional[Literal[CONCLUSIONES]] = None
    comentarios: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def conclusion_solo_al_validar(self) -> "DecisionRequest":
        if self.decision == "Validado" and self.conclusion is None:
            raise ValueError("Para validar hay que registrar la conclusión del periodista")
        if self.decision != "Validado" and self.conclusion is not None:
            raise ValueError("La conclusión solo se registra al validar")
        return self


def construir_respuesta(
    evaluacion: EvaluacionIA,
    texto: str,
    fuente: Optional[FuenteExterna] = None,
    decision: Optional[DecisionEditorial] = None,
    evidencias: Optional[List[EvidenciaAfirmacion]] = None,
) -> EvaluacionResponse:
    probabilidad = evaluacion.probabilidad_desinformacion
    if decision is not None and decision.decision_periodista not in DECISIONES:
        decision = None  # estado del flujo anterior (p. ej. 'Rechazado'): vuelve a pendientes
    evidencias = sorted(evidencias or [], key=lambda e: e.similitud, reverse=True)
    evidencia_buscada = evaluacion.nivel_evidencia_disponible is not None
    palabras = len(texto.split())
    # Con textos cortos el modelo marca casi todo como desinformación (ver
    # MIN_PALABRAS_MODELO): no se muestra un porcentaje que no mide nada
    suficiente = palabras >= settings.MIN_PALABRAS_MODELO
    return EvaluacionResponse(
        afirmacion_id=evaluacion.afirmacion_id,
        texto=texto,
        probabilidad_desinformacion=round(probabilidad, 4),
        confianza_modelo=round((1 - probabilidad) * 100) if suficiente else None,
        texto_suficiente=suficiente,
        palabras_analizadas=palabras,
        senal=clasificar_senal(probabilidad) if suficiente else "Texto insuficiente para el modelo",
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
        evidencia_buscada=evidencia_buscada,
        explicacion=(
            explicar(probabilidad, evidencias, fuente.origen if fuente else None, suficiente)
            if evidencia_buscada else []
        ),
        evidencias=[EvidenciaInfo.model_validate(e) for e in evidencias],
        decision=DecisionInfo.model_validate(decision) if decision else None,
    )


@router.post("/analyze", response_model=EvaluacionResponse)
async def analizar_afirmacion(payload: AnalizarRequest, db: AsyncSession = Depends(get_db)):
    """
    Ejecuta el clasificador sobre un texto ingresado a mano y persiste la
    Afirmacion + su EvaluacionIA. Si se pega un enlace, se descarga el
    artículo y se registra como FuenteExterna (trazabilidad, RNF-06).
    `recomendacion_sistema` siempre exige validación periodística.
    """
    texto = payload.texto.strip()
    fuente: Optional[FuenteExterna] = None
    texto_busqueda: Optional[str] = None
    if es_url(texto):
        contenido = await obtener_contenido(texto)
        if contenido is None:
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer el contenido del enlace (sitio bloqueado, muro de pago o video). Pega el texto.",
            )
        fuente = await _fuente_de_enlace(db, contenido)
        texto_busqueda = contenido.titulo or None
        texto = "\n".join(p for p in (contenido.titulo, contenido.texto) if p)

    try:
        _, evaluacion, evidencias = await evaluar_y_guardar(
            db, texto, fuente_id=fuente.id if fuente else None,
            excluir_identificador=fuente.identificador_externo if fuente else None,
            texto_busqueda=texto_busqueda,
        )
    except RuntimeError as e:
        logger.error(f"Clasificador no disponible: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error al evaluar afirmación: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al evaluar la afirmación")

    await db.commit()
    await db.refresh(evaluacion)
    return construir_respuesta(evaluacion, texto, fuente, evidencias=evidencias)


async def _fuente_de_enlace(db: AsyncSession, contenido: Contenido) -> FuenteExterna:
    identificador = _identificador(contenido.url)
    existente = (await db.execute(
        select(FuenteExterna).where(FuenteExterna.identificador_externo == identificador)
    )).scalar_one_or_none()
    if existente:
        return existente
    fuente = FuenteExterna(
        origen=_recortar(urlparse(contenido.url).netloc.removeprefix("www."), 50) or "Enlace manual",
        identificador_externo=identificador,
        titular=_recortar(contenido.titulo, 500),
        texto_procesado=contenido.texto,
        url_original=_recortar(contenido.url, 1000),
        metadatos=json.dumps({"via": "enlace_manual"}),
    )
    db.add(fuente)
    await db.flush()
    return fuente


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

    evidencias_result = await db.execute(
        select(EvidenciaAfirmacion).where(EvidenciaAfirmacion.afirmacion_id.in_(ids_afirmacion))
    )
    evidencias_por_afirmacion: dict[int, list[EvidenciaAfirmacion]] = defaultdict(list)
    for evidencia in evidencias_result.scalars().all():
        evidencias_por_afirmacion[evidencia.afirmacion_id].append(evidencia)

    return [
        construir_respuesta(
            ev, contenido, fuente,
            decision_por_afirmacion.get(ev.afirmacion_id),
            evidencias_por_afirmacion.get(ev.afirmacion_id),
        )
        for ev, contenido, fuente in filas
    ]


@router.post("/{afirmacion_id}/evidencia", response_model=EvaluacionResponse)
async def buscar_evidencia(afirmacion_id: int, db: AsyncSession = Depends(get_db)):
    """
    (Re)busca evidencia para una afirmación ya evaluada: sirve para las
    evaluadas antes del módulo RAG y para actualizar la evidencia con lo que
    verificadores y medios publicaron después. No vuelve a correr el modelo.
    """
    fila = (await db.execute(
        select(EvaluacionIA, Afirmacion.contenido, FuenteExterna)
        .join(Afirmacion, EvaluacionIA.afirmacion_id == Afirmacion.id)
        .outerjoin(FuenteExterna, Afirmacion.fuente_id == FuenteExterna.id)
        .where(EvaluacionIA.afirmacion_id == afirmacion_id)
        .order_by(EvaluacionIA.fecha_evaluacion.desc())
        .limit(1)
    )).first()
    if fila is None:
        raise HTTPException(status_code=404, detail="Afirmación no encontrada")
    evaluacion, contenido, fuente = fila

    try:
        evidencias = await buscar_y_guardar_evidencia(
            db, evaluacion, titular_de(contenido), fuente.identificador_externo if fuente else None
        )
    except Exception:
        logger.error("Error al buscar evidencia", exc_info=True)
        raise HTTPException(status_code=502, detail="No se pudo buscar evidencia en este momento")

    await db.commit()
    await db.refresh(evaluacion)
    decision = (await db.execute(
        select(DecisionEditorial)
        .where(DecisionEditorial.afirmacion_id == afirmacion_id)
        .order_by(DecisionEditorial.fecha_decision.desc())
        .limit(1)
    )).scalar_one_or_none()
    return construir_respuesta(evaluacion, contenido, fuente, decision, evidencias)


@router.post("/{afirmacion_id}/decision", response_model=DecisionInfo)
async def registrar_decision(afirmacion_id: int, payload: DecisionRequest, db: AsyncSession = Depends(get_db)):
    """
    Registra la decisión del periodista sobre una afirmación (RF-09/RF-11):
    'Validado' con su conclusión, u 'Observado' para dejarla en seguimiento.
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
        conclusion=payload.conclusion,
        comentarios=payload.comentarios,
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)

    return DecisionInfo.model_validate(decision)


@router.delete("/{afirmacion_id}", status_code=204)
async def eliminar_afirmacion(afirmacion_id: int, db: AsyncSession = Depends(get_db)):
    """
    Descarta o elimina una afirmación por completo, también de la base de
    datos: sus evaluaciones, evidencia y decisiones, y su FuenteExterna si
    ninguna otra afirmación la usa. Si la noticia sigue en el feed, vuelve a
    quedar disponible para validar. No se puede deshacer.
    """
    afirmacion = await db.get(Afirmacion, afirmacion_id)
    if afirmacion is None:
        raise HTTPException(status_code=404, detail="Afirmación no encontrada")

    noticias = (await db.execute(
        select(NoticiaFeed).where(NoticiaFeed.afirmacion_id == afirmacion_id)
    )).scalars().all()
    for noticia in noticias:
        noticia.afirmacion_id = None
        noticia.en_validacion = False

    for tabla in (EvidenciaAfirmacion, DecisionEditorial, EvaluacionIA):
        await db.execute(delete(tabla).where(tabla.afirmacion_id == afirmacion_id))
    fuente_id = afirmacion.fuente_id
    await db.delete(afirmacion)
    await db.flush()

    if fuente_id is not None:
        en_uso = await db.scalar(select(func.count()).select_from(Afirmacion).where(Afirmacion.fuente_id == fuente_id))
        if not en_uso:
            await db.execute(delete(FuenteExterna).where(FuenteExterna.id == fuente_id))

    await db.commit()

    # Los paneles abiertos quitan la marca "En validación" de la tarjeta
    for noticia in noticias:
        await feed_bus.publish(serializar_feed(noticia))
    return Response(status_code=204)
