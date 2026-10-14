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

# Verificadores con RSS público (probados). AFP Factual y Colombiacheck
# bloquean su RSS; llegan por Google Fact Check. Formato: (nombre, url)
VERIFICADORES_RSS = [
    ("Maldito Bulo", "https://maldita.es/malditobulo/feed/"),
    ("Chequeado", "https://chequeado.com/feed/"),
    ("Factchequeado", "https://factchequeado.com/feed/"),
    ("Fast Check", "https://fastcheck.cl/feed/"),
    ("Ecuador Chequea", "https://ecuadorchequea.com/feed/"),
    ("Cotejo", "https://cotejo.info/feed/"),
    ("Verificado", "https://verificado.com.mx/feed/"),
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

    async def _fetch_varios(self, fuentes: List[tuple]) -> List[tuple]:
        """
        Lee varios feeds a la vez; cada fuente es (url, *datos) y devuelve
        (entrada, *datos). Un feed caído solo se registra: no frena a los demás.
        """
        resultados = await asyncio.gather(*(self.fetch(url) for url, *_ in fuentes), return_exceptions=True)
        entradas = []
        for (url, *datos), resultado in zip(fuentes, resultados):
            if isinstance(resultado, Exception):
                logger.warning(f"[rss] No se pudo leer {datos[0]} ({url}): {resultado!r}")
                continue
            entradas.extend((entrada, *datos) for entrada in resultado)
        return entradas

    async def fetch_medios(self) -> List[tuple]:
        """Entradas de todos los medios como (entrada, medio, país)."""
        return await self._fetch_varios([(url, medio, pais) for medio, pais, url in MEDIOS_RSS])

    async def fetch_verificadores(self) -> List[tuple]:
        """Entradas de todos los verificadores como (entrada, verificador)."""
        return await self._fetch_varios([(url, nombre) for nombre, url in VERIFICADORES_RSS])

    async def fetch_reddit(self) -> List[Dict[str, Any]]:
        return await self.fetch(REDDIT_RSS_URL.format(subs="+".join(SUBREDDITS)))
