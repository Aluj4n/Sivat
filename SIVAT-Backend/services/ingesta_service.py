import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.eventbus import internacionales_bus
from models.entities import FuenteExterna
from services.gdelt_service import GDELTService
from services.normalizacion import (
    normalizar_gdelt,
    normalizar_x,
    normalizar_youtube,
    serializar_noticia,
)
from services.x_service import XService
from services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)

QUERY_GDELT_INTL_DEFAULT = "sourcelang:spanish -peru"
QUERY_X_INTL_DEFAULT = "world news OR rumor -peru"
QUERY_YOUTUBE_INTL_DEFAULT = "breaking news world"


async def guardar_registros(
    db: AsyncSession, registros: List[Dict[str, Any]], notificar: bool = False
) -> int:
    """
    Persiste registros normalizados en FuenteExterna evitando duplicados por
    identificador_externo. Si `notificar` es True, publica cada registro nuevo
    en el bus de eventos para que el panel Internacionales lo reciba en vivo.
    """
    registros_validos = [r for r in registros if r.get("identificador_externo")]
    if not registros_validos:
        return 0

    ids_externos = [r["identificador_externo"] for r in registros_validos]
    existentes = await db.execute(
        select(FuenteExterna.identificador_externo).where(
            FuenteExterna.identificador_externo.in_(ids_externos)
        )
    )
    ids_existentes = {row[0] for row in existentes.all()}

    nuevas_entidades: List[FuenteExterna] = []
    for registro in registros_validos:
        if registro["identificador_externo"] in ids_existentes:
            continue
        entidad = FuenteExterna(**registro)
        db.add(entidad)
        nuevas_entidades.append(entidad)

    if not nuevas_entidades:
        return 0

    await db.commit()

    if notificar:
        for entidad in nuevas_entidades:
            await db.refresh(entidad)
            if entidad.pais != "PE":
                await internacionales_bus.publish(serializar_noticia(entidad))

    return len(nuevas_entidades)


async def ingerir_gdelt_internacional(db: AsyncSession, query: str = QUERY_GDELT_INTL_DEFAULT) -> int:
    data = await GDELTService().fetch_news_internacional(query=query)
    registros = [normalizar_gdelt(articulo) for articulo in data]
    return await guardar_registros(db, registros, notificar=True)


async def ingerir_x_internacional(db: AsyncSession, query: str = QUERY_X_INTL_DEFAULT) -> int:
    data = await XService().search_recent_tweets(query=query)
    registros = [normalizar_x(tweet) for tweet in data]
    return await guardar_registros(db, registros, notificar=True)


async def ingerir_youtube_internacional(db: AsyncSession, query: str = QUERY_YOUTUBE_INTL_DEFAULT) -> int:
    data = await YouTubeService().search_videos(query=query)
    registros = [normalizar_youtube(item) for item in data]
    return await guardar_registros(db, registros, notificar=True)


# Usadas por el ciclo automático en segundo plano (main.py) para sondear
# las fuentes de forma continua sin depender de que alguien abra el panel.
# GDELT se sondea por separado (ver main.py): es gratuito, sin API key, y
# bloquea la IP por tiempo prolongado si se le insiste con la misma frecuencia
# que X/YouTube.
INGESTORES_INTERNACIONALES = (
    ingerir_x_internacional,
    ingerir_youtube_internacional,
)
