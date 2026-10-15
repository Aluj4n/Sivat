"""
Descarga el contenido completo de una noticia al validarla. El modelo se
entrenó con artículos completos (~340 palabras) y con solo el titular no
distingue nada (ver ml/), así que el feed guarda el titular y aquí se obtiene
el cuerpo únicamente para las noticias que un periodista elige revisar.
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx
import trafilatura

from services.gdelt_service import USER_AGENT

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 15
MAX_CARACTERES = 20000
_RE_URL = re.compile(r"^https?://\S+$")

# Fuentes cuya url_original no es la noticia: se descarga el enlace que comparten
ORIGENES_CON_ENLACE_EXTERNO = {"Reddit", "Bluesky"}
# Sin texto descargable (el contenido está en el video)
ORIGENES_SIN_CONTENIDO = {"YouTube", "X"}


@dataclass
class Contenido:
    texto: str
    titulo: Optional[str]
    url: str

    @property
    def palabras(self) -> int:
        return len(self.texto.split())


def es_url(texto: str) -> bool:
    return bool(_RE_URL.match(texto.strip()))


def url_a_descargar(origen: Optional[str], url_original: Optional[str], metadatos: Optional[str]) -> Optional[str]:
    if origen in ORIGENES_SIN_CONTENIDO:
        return None
    if origen in ORIGENES_CON_ENLACE_EXTERNO:
        try:
            enlace = json.loads(metadatos or "{}").get("enlace_externo")
        except ValueError:
            enlace = None
        # Imágenes y videos de Reddit no tienen texto que extraer
        if not enlace or re.search(r"(i|v)\.redd\.it|reddit\.com/gallery|bsky\.app", enlace):
            return None
        return enlace
    return url_original


def _extraer(html: str) -> tuple[str, Optional[str]]:
    texto = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True) or ""
    metadatos = trafilatura.extract_metadata(html)
    return texto, (metadatos.title if metadatos else None)


async def obtener_contenido(url: str) -> Optional[Contenido]:
    """
    Cuerpo del artículo sin menús, publicidad ni comentarios. Devuelve None si
    el sitio no responde, bloquea la descarga o no hay texto (muro de pago,
    página de video): quien llama sigue con el titular y el resumen.
    """
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SEGUNDOS, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        texto, titulo = await asyncio.to_thread(_extraer, response.text)
    except Exception as e:
        logger.warning(f"[contenido] No se pudo extraer {url}: {e!r}")
        return None

    texto = texto.strip()[:MAX_CARACTERES]
    return Contenido(texto=texto, titulo=titulo, url=str(response.url)) if texto else None
