from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from services.gdelt_service import USER_AGENT


class BlueskyService:
    # AppView pública: la búsqueda no exige cuenta (public.api.bsky.app sí devuelve 403)
    SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"

    async def search_publicados_desde(
        self, terminos: List[str], publicado_desde: datetime, idioma: str = "es"
    ) -> List[Dict[str, Any]]:
        """
        Posts en `idioma` publicados desde `publicado_desde` que contengan alguno
        de los `terminos`. El buscador no admite OR, así que se hace una
        búsqueda por término; los repetidos se descartan al guardar en el feed.
        """
        desde = publicado_desde.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        posts: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            for termino in terminos:
                response = await client.get(
                    self.SEARCH_URL,
                    params={"q": termino, "lang": idioma, "sort": "latest", "since": desde, "limit": 100},
                )
                response.raise_for_status()
                posts.extend(response.json().get("posts", []))
        return posts
