import asyncio
import logging
from typing import Any, Dict, List

import feedparser
import httpx

from services.gdelt_service import USER_AGENT

logger = logging.getLogger(__name__)

# Medios internacionales en español con RSS público (probados; CNN en Español
# y EFE no exponen un feed accesible). Formato: (nombre visible, país, url)
MEDIOS_RSS = [
    ("BBC Mundo", "United Kingdom", "https://feeds.bbci.co.uk/mundo/rss.xml"),
    ("DW Español", "Germany", "https://rss.dw.com/xml/rss-sp-all"),
    ("France 24", "France", "https://www.france24.com/es/rss"),
    ("El País", "Spain", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada"),
    ("Infobae", "Argentina", "https://www.infobae.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("Europa Press", "Spain", "https://www.europapress.es/rss/rss.aspx?ch=00069"),
    ("Euronews", "France", "https://es.euronews.com/rss"),
]

# Subreddits en español (sin r/PERU). Reddit bloquea su API JSON sin OAuth,
# pero el RSS de un multireddit trae todos en una sola petición.
SUBREDDITS = ["noticias", "LatinoAmerica", "argentina", "mexico", "chile", "Colombia", "vzla", "es", "uruguay", "ecuador"]
REDDIT_RSS_URL = "https://www.reddit.com/r/{subs}/new/.rss?limit=100"


class RSSService:
    async def fetch(self, url: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        feed = await asyncio.to_thread(feedparser.parse, response.content)
        return list(feed.entries)

    async def fetch_medios(self) -> List[tuple]:
        """
        Entradas de todos los medios como (entrada, medio, país). Un feed caído
        solo se registra: no impide traer los demás.
        """
        resultados = await asyncio.gather(
            *(self.fetch(url) for _, _, url in MEDIOS_RSS), return_exceptions=True
        )
        entradas = []
        for (medio, pais, url), resultado in zip(MEDIOS_RSS, resultados):
            if isinstance(resultado, Exception):
                logger.warning(f"[rss] No se pudo leer {medio} ({url}): {resultado!r}")
                continue
            entradas.extend((entrada, medio, pais) for entrada in resultado)
        return entradas

    async def fetch_reddit(self) -> List[Dict[str, Any]]:
        return await self.fetch(REDDIT_RSS_URL.format(subs="+".join(SUBREDDITS)))
