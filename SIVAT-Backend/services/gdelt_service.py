import httpx
from typing import List, Dict, Any

class GDELTService:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def fetch_news_peru(self) -> List[Dict[str, Any]]:
        """
        Fetches the latest news related to Peru using the GDELT DOC 2.0 API.
        """
        return await self._fetch(query="peru", maxrecords=50)

    async def fetch_news_internacional(self, query: str = "sourcelang:spanish -peru") -> List[Dict[str, Any]]:
        """
        Fetches trending international news/rumors (excluding Peru-specific coverage)
        using the GDELT DOC 2.0 API, for the "Internacionales" panel.
        """
        return await self._fetch(query=query, maxrecords=50)

    async def _fetch(self, query: str, maxrecords: int = 50) -> List[Dict[str, Any]]:
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": maxrecords,
            "sort": "hybridrel",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
