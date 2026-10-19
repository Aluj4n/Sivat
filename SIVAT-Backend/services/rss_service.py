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

# Medios peruanos (probados) para el panel Perú. Su sección internacional va
# a Internacionales (ver normalizacion._pais_medio_peruano). La República no
# tiene feed general, solo por sección. Perú21 bloquea el RSS (403).
MEDIOS_RSS_PERU = [
    ("Canal N", "Peru", "https://canaln.pe/feed"),
    ("RPP", "Peru", "https://rpp.pe/rss"),
    ("Andina", "Peru", "https://andina.pe/agencia/rss/0.xml"),
    ("El Comercio", "Peru", "https://elcomercio.pe/arcio/rss/"),
    ("La República", "Peru", "https://larepublica.pe/rss/politica.xml"),
    ("La República", "Peru", "https://larepublica.pe/rss/sociedad.xml"),
    ("Gestión", "Peru", "https://gestion.pe/arcio/rss/"),
    ("Correo", "Peru", "https://diariocorreo.pe/arcio/rss/"),
    ("Infobae Perú", "Peru", "https://www.infobae.com/arc/outboundfeeds/rss/category/peru/?outputType=xml"),
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
    ("Verificador LR", "https://larepublica.pe/rss/verificador.xml"),
]

# Subreddits en español. Reddit bloquea su API JSON sin OAuth, pero el RSS de
# un multireddit trae todos en una sola petición (r/PERU va al panel Perú).
SUBREDDITS = ["PERU", "noticias", "LatinoAmerica", "argentina", "mexico", "chile", "Colombia", "vzla", "es", "uruguay", "ecuador"]
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
        """Entradas de todos los medios, extranjeros y peruanos, como (entrada, medio, país)."""
        return await self._fetch_varios([(url, medio, pais) for medio, pais, url in MEDIOS_RSS + MEDIOS_RSS_PERU])

    async def fetch_verificadores(self) -> List[tuple]:
        """Entradas de todos los verificadores como (entrada, verificador)."""
        return await self._fetch_varios([(url, nombre) for nombre, url in VERIFICADORES_RSS])

    async def fetch_reddit(self) -> List[Dict[str, Any]]:
        return await self.fetch(REDDIT_RSS_URL.format(subs="+".join(SUBREDDITS)))
