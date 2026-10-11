import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.eventbus import internacionales_bus
from models.entities import FuenteExterna, NoticiaFeed
from services.bluesky_service import BlueskyService
from services.gdelt_service import GDELTService
from services.normalizacion import (
    es_noticia_peruana,
    es_post_reddit_de_texto,
    normalizar_bluesky,
    normalizar_gdelt,
    normalizar_gdelt_gkg,
    normalizar_reddit,
    normalizar_rss,
    normalizar_x,
    normalizar_youtube,
    serializar_feed,
)
from services.rss_service import RSSService
from services.x_service import XService
from services.youtube_service import YouTubeService

logger = logging.getLogger(__name__)

QUERY_GDELT_INTL_DEFAULT = "sourcelang:spanish -peru"
QUERY_X_INTL_DEFAULT = "world news OR rumor -peru"
# Búsqueda amplia (operadores | y - de YouTube): todo lo noticioso en español, sin Perú
QUERY_YOUTUBE_INTL_DEFAULT = "noticias|última hora|internacional|news -peru -perú"

# Bluesky no admite OR: una búsqueda por término (deduplicadas al guardar)
TERMINOS_BLUESKY = ["noticias", "urgente", "rumor", "alerta", "denuncian", "confirmado", "viral", "falso"]
LARGO_MINIMO_POST = 40

# Hasta dónde mirar atrás en la primera búsqueda tras arrancar el backend
_ultima_busqueda_youtube: datetime | None = None
_ultima_busqueda_bluesky: datetime | None = None


async def guardar_registros(db: AsyncSession, registros: List[Dict[str, Any]]) -> int:
    """
    Persiste registros en FuenteExterna (uso actual: feed Perú vía api/ingesta.py).
    El panel Internacionales ya no escribe aquí: usa NoticiaFeed.
    """
    registros_validos = [r for r in registros if r.get("identificador_externo")]
    if not registros_validos:
        return 0

    ids_externos = [r["identificador_externo"] for r in registros_validos]
    existentes = await db.execute(
        select(FuenteExterna.identificador_externo).where(FuenteExterna.identificador_externo.in_(ids_externos))
    )
    ids_existentes = {row[0] for row in existentes.all()}

    nuevos = 0
    for registro in registros_validos:
        if registro["identificador_externo"] in ids_existentes:
            continue
        db.add(FuenteExterna(**registro))
        nuevos += 1

    if nuevos:
        await db.commit()
    return nuevos


async def guardar_en_feed(db: AsyncSession, registros: List[Dict[str, Any]]) -> int:
    """
    Guarda en el feed temporal solo lo internacional y aún no visto, y lo
    publica por SSE para que aparezca primero en el panel sin recargar.
    """
    # Los RSS repiten artículos de días atrás: lo que ya superó la retención
    # volvería a entrar tras cada limpieza, así que se descarta aquí.
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    registros_validos = [
        r for r in registros
        if r.get("identificador_externo")
        and not es_noticia_peruana(r)
        and not (r.get("fecha_publicacion") and r["fecha_publicacion"] < limite)
    ]
    if not registros_validos:
        return 0

    # Una misma respuesta de la API puede repetir el mismo artículo
    unicos = {r["identificador_externo"]: r for r in registros_validos}

    existentes = await db.execute(
        select(NoticiaFeed.identificador_externo).where(NoticiaFeed.identificador_externo.in_(list(unicos)))
    )
    ids_existentes = {row[0] for row in existentes.all()}

    nuevas: List[NoticiaFeed] = []
    for identificador, registro in unicos.items():
        if identificador in ids_existentes:
            continue
        noticia = NoticiaFeed(**registro)
        db.add(noticia)
        nuevas.append(noticia)

    if not nuevas:
        return 0

    await db.commit()
    for noticia in nuevas:
        await db.refresh(noticia)
        await internacionales_bus.publish(serializar_feed(noticia))

    return len(nuevas)


async def ingerir_gdelt_internacional(db: AsyncSession) -> int:
    """
    Lee el archivo GKG de 15 min (noticias en español). Se consulta cada 3 min
    para mostrar cada archivo apenas sale; si no hay uno nuevo, no descarga nada.
    """
    data = await GDELTService().fetch_gkg_reciente(idioma="spa")
    return await guardar_en_feed(db, [normalizar_gdelt_gkg(articulo) for articulo in data])


async def ingerir_gdelt_doc_api(db: AsyncSession, query: str = QUERY_GDELT_INTL_DEFAULT) -> int:
    # Búsqueda por DOC API, solo para disparo manual (suele responder 429)
    data = await GDELTService().fetch_news_internacional(query=query)
    return await guardar_en_feed(db, [normalizar_gdelt(articulo) for articulo in data])


async def ingerir_youtube_internacional(db: AsyncSession, query: str = QUERY_YOUTUBE_INTL_DEFAULT) -> int:
    """
    Trae todo lo publicado desde la búsqueda anterior (máx. 50 por llamada),
    así cada consulta suma videos nuevos en vez de repetir los mismos.
    """
    global _ultima_busqueda_youtube

    ahora = datetime.now(timezone.utc)
    desde = _ultima_busqueda_youtube or ahora - timedelta(seconds=settings.INTERVAL_INGESTA_YOUTUBE_SEGUNDOS)
    data = await YouTubeService().search_publicados_desde(query=query, publicado_desde=desde)
    _ultima_busqueda_youtube = ahora

    return await guardar_en_feed(db, [normalizar_youtube(item) for item in data])


async def ingerir_bluesky_internacional(db: AsyncSession) -> int:
    """
    Posts en español con términos de noticia o rumor publicados desde la
    búsqueda anterior. Buscar todo el español traería ~2000 posts/hora de
    conversación; los términos dejan lo que suele requerir verificación.
    """
    global _ultima_busqueda_bluesky

    ahora = datetime.now(timezone.utc)
    desde = _ultima_busqueda_bluesky or ahora - timedelta(seconds=settings.INTERVAL_INGESTA_BLUESKY_SEGUNDOS)
    data = await BlueskyService().search_publicados_desde(TERMINOS_BLUESKY, publicado_desde=desde)
    _ultima_busqueda_bluesky = ahora

    # Descarta posts muy cortos (saludos, reacciones): no hay afirmación que verificar
    registros = [normalizar_bluesky(post) for post in data]
    return await guardar_en_feed(db, [r for r in registros if len(r["texto_procesado"]) >= LARGO_MINIMO_POST])


async def ingerir_reddit_internacional(db: AsyncSession) -> int:
    # Solo posts que enlazan noticia, imagen o video; los de texto son conversación
    data = await RSSService().fetch_reddit()
    return await guardar_en_feed(
        db, [normalizar_reddit(entrada) for entrada in data if not es_post_reddit_de_texto(entrada)]
    )


async def ingerir_rss_medios(db: AsyncSession) -> int:
    data = await RSSService().fetch_medios()
    return await guardar_en_feed(db, [normalizar_rss(entrada, medio, pais) for entrada, medio, pais in data])


async def ingerir_x_internacional(db: AsyncSession, query: str = QUERY_X_INTL_DEFAULT) -> int:
    # Fuera del ciclo automático por ahora (plan de X pendiente); solo disparo manual.
    data = await XService().search_recent_tweets(query=query)
    return await guardar_en_feed(db, [normalizar_x(tweet) for tweet in data])


async def limpiar_feed_vencido(db: AsyncSession) -> int:
    """
    Borra del feed lo capturado hace más de RETENCION_FEED_HORAS. Lo validado
    ya vive en FuenteExterna, así que también puede salir del feed.
    """
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    resultado = await db.execute(delete(NoticiaFeed).where(NoticiaFeed.fecha_captura < limite))
    await db.commit()
    return resultado.rowcount or 0
