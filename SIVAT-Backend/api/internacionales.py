import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from core.eventbus import internacionales_bus
from db.session import get_db
from models.entities import FuenteExterna
from services.normalizacion import serializar_noticia

router = APIRouter()

# Cada cuántos segundos se envía un "ping" para mantener viva la conexión SSE
SSE_HEARTBEAT_SEGUNDOS = 15


@router.get("/internacionales")
async def obtener_internacionales(db: AsyncSession = Depends(get_db)):
    """
    Devuelve las noticias/rumores ingeridos desde GDELT, X y YouTube
    para el panel "Internacionales" (contenido no originado en Perú),
    ordenados con lo más reciente primero.
    """
    resultado = await db.execute(
        select(FuenteExterna)
        .where(FuenteExterna.pais != "PE")
        .order_by(FuenteExterna.fecha_publicacion.desc().nullslast())
        .limit(30)
    )
    noticias = resultado.scalars().all()
    return [serializar_noticia(noticia) for noticia in noticias]


@router.get("/internacionales/stream")
async def stream_internacionales(request: Request):
    """
    Server-Sent Events: empuja cada noticia/rumor internacional nuevo apenas
    se ingiere, para que aparezca primero en el panel sin recargar la página.
    """

    async def generador():
        queue = internacionales_bus.subscribe()
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
            internacionales_bus.unsubscribe(queue)

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
