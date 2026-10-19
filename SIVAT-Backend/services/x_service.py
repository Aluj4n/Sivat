import httpx
from typing import List, Dict, Any
from core.config import settings
from core.security import sanitize_text

class XService:
    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.X_API_BEARER_TOKEN}"
        }

    async def search_recent_tweets(self, query: str = "peru", max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Searches recent tweets based on a query using X API v2.
        Applies sanitization to the text.
        """
        url = f"{self.BASE_URL}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            tweets = data.get("data", [])
            for tweet in tweets:
                # Sanitize text to protect PII
                tweet["text"] = sanitize_text(tweet.get("text", ""))
                
            return tweets
