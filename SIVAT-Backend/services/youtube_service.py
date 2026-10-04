import httpx
from typing import List, Dict, Any
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
