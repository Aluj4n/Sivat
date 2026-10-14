from typing import Any, Dict, List

import httpx

from core.config import settings
from services.gdelt_service import USER_AGENT


class GoogleFactCheckService:
    """
    Google Fact Check Tools: verificaciones (ClaimReview) publicadas por
    verificadores de todo el mundo, entre ellos AFP Factual y Colombiacheck,
    cuyos RSS no son accesibles. Usa la misma clave de Google Cloud que YouTube
    salvo que se configure una propia.
    """
    SEARCH_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    async def search(self, query: str, idioma: str = "es", page_size: int = 10) -> List[Dict[str, Any]]:
        params = {
            "query": query,
            "languageCode": idioma,
            "pageSize": page_size,
            "key": settings.GOOGLE_FACTCHECK_API_KEY or settings.YOUTUBE_API_KEY,
        }
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            return response.json().get("claims", [])
