import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.verificacion import EvaluacionResponse, construir_respuesta
from core.config import settings
from core.eventbus import feed_bus
from db.session import get_db
from models.entities import FuenteExterna, NoticiaFeed
from services.contenido_service import obtener_contenido, url_a_descargar
from services.normalizacion import PAISES_PERU, serializar_feed
from services.verificacion_service import evaluar_y_guardar

router = APIRouter()
logger = logging.getLogger(__name__)

# Cada cuántos segundos se envía un "ping" para mantener viva la conexión SSE
SSE_HEARTBEAT_SEGUNDOS = 15
MAX_LARGO_TEXTO = 20000


async def _feed_del_panel(db: AsyncSession, peru: bool) -> list:
    """
    Feed temporal de un panel: solo lo capturado en las últimas
    RETENCION_FEED_HORAS, más reciente primero. Nada de esto está en
    FuenteExterna hasta que alguien lo valide.
    """
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    es_peru = func.lower(NoticiaFeed.pais).in_(PAISES_PERU)
    resultado = await db.execute(
        select(NoticiaFeed)
        .where(NoticiaFeed.fecha_captura >= limite)
        .where(es_peru if peru else or_(NoticiaFeed.pais.is_(None), not_(es_peru)))
        .order_by(NoticiaFeed.fecha_publicacion.desc().nullslast(), NoticiaFeed.id.desc())
        .limit(100)
    )
    return [serializar_feed(noticia) for noticia in resultado.scalars().all()]


@router.get("/internacionales")
async def obtener_internacionales(db: AsyncSession = Depends(get_db)):
    return await _feed_del_panel(db, peru=False)


@router.get("/peru")
async def obtener_peru(db: AsyncSession = Depends(get_db)):
    return await _feed_del_panel(db, peru=True)


@router.post("/feed/{feed_id}/validar", response_model=EvaluacionResponse)
@router.post("/internacionales/{feed_id}/validar", response_model=EvaluacionResponse, include_in_schema=False)
async def enviar_a_validacion(feed_id: int, db: AsyncSession = Depends(get_db)):
    """
    El periodista elige una noticia del feed: se guarda de forma permanente en
    FuenteExterna, se crea su Afirmacion enlazada (RNF-06), se corre el
    clasificador y queda en la cola de la vista Validación.
    """
    # Bloquea la fila para que dos clics simultáneos no la envíen dos veces
    noticia = await db.get(NoticiaFeed, feed_id, with_for_update=True)
    if noticia is None:
        raise HTTPException(status_code=404, detail="La noticia ya no está en el feed (pudo vencer a las 24 h)")
    if noticia.en_validacion:
        raise HTTPException(status_code=409, detail="Esta noticia ya fue enviada a validación")

    existente = await db.execute(
        select(FuenteExterna).where(FuenteExterna.identificador_externo == noticia.identificador_externo)
    )
    fuente = existente.scalar_one_or_none()
    if fuente is None:
        fuente = FuenteExterna(
            origen=noticia.origen,
            identificador_externo=noticia.identificador_externo,
            texto_procesado=noticia.texto_procesado,
            metadatos=noticia.metadatos,
            titular=noticia.titular,
            imagen_url=noticia.imagen_url,
            url_original=noticia.url_original,
            pais=noticia.pais,
            fecha_publicacion=noticia.fecha_publicacion,
        )
        db.add(fuente)
        await db.flush()

    # El modelo necesita el artículo completo: se descarga solo ahora, para la
    # noticia elegida. Si no se puede, se sigue con el titular y el resumen.
    titular = (noticia.titular or "").strip()
    url = url_a_descargar(noticia.origen, noticia.url_original, noticia.metadatos)
    contenido = await obtener_contenido(url) if url else None
    if contenido:
        cuerpo = contenido.texto
        fuente.texto_procesado = contenido.texto
    elif noticia.texto_procesado and noticia.texto_procesado != titular:
        cuerpo = noticia.texto_procesado
    else:
        cuerpo = ""
    texto = "\n".join(p for p in (titular, cuerpo) if p).strip()[:MAX_LARGO_TEXTO]

    try:
        afirmacion, evaluacion, evidencias = await evaluar_y_guardar(
            db, texto, fuente_id=fuente.id, excluir_identificador=noticia.identificador_externo,
            texto_busqueda=titular or None,
        )
    except RuntimeError as e:
        logger.error(f"Clasificador no disponible: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    noticia.en_validacion = True
    noticia.afirmacion_id = afirmacion.id
    await db.commit()
    await db.refresh(evaluacion)
    await db.refresh(noticia)

    # Avisa a los demás paneles abiertos que esta tarjeta ya está en validación
    await feed_bus.publish(serializar_feed(noticia))

    return construir_respuesta(evaluacion, texto, fuente, evidencias=evidencias)


@router.get("/feed/stream")
@router.get("/internacionales/stream", include_in_schema=False)
async def stream_feed(request: Request):
    """
    Server-Sent Events: empuja cada noticia nueva del feed apenas se captura,
    y los cambios de estado (p. ej. "en validación") de las ya mostradas.
    Cada evento trae su "panel" (peru | internacional) para que cada vista
    se quede con lo suyo.
    """

    async def generador():
        queue = feed_bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evento = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_SEGUNDOS)
                    yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            feed_bus.unsubscribe(queue)

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
