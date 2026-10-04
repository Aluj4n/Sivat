import logging
import traceback

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from db.session import get_db
from services.gdelt_service import GDELTService
from services.x_service import XService
from services.youtube_service import YouTubeService
from services.normalizacion import normalizar_gdelt, normalizar_x, normalizar_youtube
from services.ingesta_service import (
    guardar_registros,
    ingerir_gdelt_internacional,
    ingerir_x_internacional,
    ingerir_youtube_internacional,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/gdelt")
async def ingest_gdelt(db: AsyncSession = Depends(get_db)):
    """
    Triggers data ingestion from GDELT Project (noticias de Perú).
    """
    service = GDELTService()
    try:
        data = await service.fetch_news_peru()
        registros = [normalizar_gdelt(articulo, pais_default="PE") for articulo in data]
        nuevos = await guardar_registros(db, registros)
        return {"status": "success", "source": "GDELT", "articles_fetched": len(data), "nuevos_guardados": nuevos}
    except httpx.HTTPStatusError as e:
        logger.error(f"GDELT HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from GDELT: {e.response.text}")
    except Exception as e:
        logger.error(f"GDELT Internal Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {repr(e)}")


@router.get("/internacional/gdelt")
async def ingest_gdelt_internacional(query: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    Dispara manualmente una ingesta desde GDELT Project para el panel "Internacionales".
    El ciclo automático en segundo plano ya hace esto solo; este endpoint es útil
    para forzar una actualización inmediata.
    """
    try:
        kwargs = {"query": query} if query else {}
        nuevos = await ingerir_gdelt_internacional(db, **kwargs)
        return {"status": "success", "source": "GDELT", "nuevos_guardados": nuevos}
    except httpx.HTTPStatusError as e:
        logger.error(f"GDELT HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from GDELT: {e.response.text}")
    except Exception as e:
        logger.error(f"GDELT Internal Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {repr(e)}")


@router.get("/x")
async def ingest_x(query: str = "peru", db: AsyncSession = Depends(get_db)):
    """
    Triggers data ingestion from X (Twitter) API.
    """
    service = XService()
    try:
        data = await service.search_recent_tweets(query=query)
        registros = [normalizar_x(tweet, pais_default="PE") for tweet in data]
        nuevos = await guardar_registros(db, registros)
        return {"status": "success", "source": "X", "tweets_fetched": len(data), "nuevos_guardados": nuevos}
    except httpx.HTTPStatusError as e:
        logger.error(f"X HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from X API: {e.response.text}")
    except Exception as e:
        logger.error(f"X Internal Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {repr(e)}")


@router.get("/internacional/x")
async def ingest_x_internacional(query: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    Dispara manualmente una ingesta desde X (Twitter) para el panel "Internacionales".
    """
    try:
        kwargs = {"query": query} if query else {}
        nuevos = await ingerir_x_internacional(db, **kwargs)
        return {"status": "success", "source": "X", "nuevos_guardados": nuevos}
    except httpx.HTTPStatusError as e:
        logger.error(f"X HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from X API: {e.response.text}")
    except Exception as e:
        logger.error(f"X Internal Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {repr(e)}")


@router.get("/youtube")
async def ingest_youtube(query: str = "noticias peru", db: AsyncSession = Depends(get_db)):
    """
    Triggers data ingestion from YouTube Data API.
    """
    service = YouTubeService()
    try:
        data = await service.search_videos(query=query)
        registros = [normalizar_youtube(item, pais_default="PE") for item in data]
        nuevos = await guardar_registros(db, registros)
        return {"status": "success", "source": "YouTube", "videos_fetched": len(data), "nuevos_guardados": nuevos}
    except httpx.HTTPStatusError as e:
        logger.error(f"YouTube HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from YouTube API: {e.response.text}")
    except Exception as e:
        logger.error(f"YouTube Internal Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {repr(e)}")


@router.get("/internacional/youtube")
async def ingest_youtube_internacional(query: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    Dispara manualmente una ingesta desde YouTube para el panel "Internacionales".
    """
    try:
        kwargs = {"query": query} if query else {}
        nuevos = await ingerir_youtube_internacional(db, **kwargs)
        return {"status": "success", "source": "YouTube", "nuevos_guardados": nuevos}
    except httpx.HTTPStatusError as e:
        logger.error(f"YouTube HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from YouTube API: {e.response.text}")
    except Exception as e:
        logger.error(f"YouTube Internal Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {repr(e)}")
