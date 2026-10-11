from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from core.config import settings


class YouTubeService:
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY

    async def search_videos(self, query: str = "noticias peru", max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Searches for YouTube videos matching the query.
        """
        url = f"{self.BASE_URL}/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            return data.get("items", [])

    async def search_publicados_desde(
        self, query: str, publicado_desde: datetime, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda amplia de videos publicados desde `publicado_desde`, más recientes
        primero. Cuesta 100 unidades de cuota sin importar `max_results` (máx. 50),
        así que se pide el máximo para no perder videos entre ciclos.
        """
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "relevanceLanguage": "es",
            "publishedAfter": publicado_desde.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "maxResults": max_results,
            "key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.BASE_URL}/search", params=params)
            response.raise_for_status()
            return response.json().get("items", [])
