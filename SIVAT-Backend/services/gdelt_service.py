import asyncio
import csv
import io
import re
import zipfile

import httpx
from typing import List, Dict, Any, Optional

USER_AGENT = "SIVAT/1.0 (proyecto academico UPN - verificacion periodistica)"

# GDELT publica cada 15 min un GKG con lo traducido al inglés (todo lo no
# inglés). Son archivos estáticos: sin el límite ni los 429 de la DOC API.
LASTUPDATE_TRADUCCION_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate-translation.txt"

# Columnas del GKG 2.1 que usamos
_COL_FECHA, _COL_FUENTE, _COL_URL, _COL_IMAGEN, _COL_TRADUCCION, _COL_EXTRAS = 1, 3, 4, 18, 25, 26
_RE_TITULO = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)


def _parsear_gkg(contenido_zip: bytes, idioma: str) -> List[Dict[str, Any]]:
    csv.field_size_limit(10**9)
    with zipfile.ZipFile(io.BytesIO(contenido_zip)) as z:
        with z.open(z.namelist()[0]) as f:
            lector = csv.reader(io.TextIOWrapper(f, "utf-8", "replace"), delimiter="\t")
            articulos = []
            for fila in lector:
                if len(fila) <= _COL_EXTRAS or f"srclc:{idioma}" not in fila[_COL_TRADUCCION]:
                    continue
                titulo = _RE_TITULO.search(fila[_COL_EXTRAS])
                if not titulo:
                    continue
                articulos.append({
                    "url": fila[_COL_URL],
                    "titulo": titulo.group(1),
                    "imagen": fila[_COL_IMAGEN] or None,
                    "dominio": fila[_COL_FUENTE],
                    "fecha": fila[_COL_FECHA],
                })
            return articulos


class GDELTService:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    # Último archivo GKG procesado: evita descargar el mismo dos veces
    _ultimo_archivo_gkg: Optional[str] = None

    async def fetch_gkg_reciente(self, idioma: str = "spa") -> List[Dict[str, Any]]:
        """
        Artículos del último archivo GKG de 15 min en el idioma indicado.
        Devuelve [] si GDELT aún no publicó un archivo nuevo desde la última vez.
        """
        async with httpx.AsyncClient(
            timeout=60.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        ) as client:
            indice = await client.get(LASTUPDATE_TRADUCCION_URL)
            indice.raise_for_status()
            url_gkg = next(
                (linea.split()[-1] for linea in indice.text.splitlines() if linea.endswith(".gkg.csv.zip")),
                None,
            )
            if not url_gkg or url_gkg == GDELTService._ultimo_archivo_gkg:
                return []

            archivo = await client.get(url_gkg)
            archivo.raise_for_status()

        articulos = await asyncio.to_thread(_parsear_gkg, archivo.content, idioma)
        GDELTService._ultimo_archivo_gkg = url_gkg
        return articulos

    async def fetch_news_peru(self) -> List[Dict[str, Any]]:
        """
        Fetches the latest news related to Peru using the GDELT DOC 2.0 API.
        """
        return await self._fetch(query="peru", maxrecords=50)

    async def fetch_news_internacional(self, query: str = "sourcelang:spanish -peru") -> List[Dict[str, Any]]:
        """
        Búsqueda por DOC API (uso manual). El ciclo automático usa
        fetch_gkg_reciente porque la DOC API devuelve 429 de forma sostenida.
        """
        return await self._fetch(query=query, maxrecords=75, timespan="1h", sort="datedesc")

    async def _fetch(
        self, query: str, maxrecords: int = 50, timespan: str | None = None, sort: str = "hybridrel"
    ) -> List[Dict[str, Any]]:
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": maxrecords,
            "sort": sort,
        }
        if timespan:
            params["timespan"] = timespan

        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(self.BASE_URL, params=params)
            # GDELT responde 429 de forma intermitente aunque se respete su límite
            # (servicio saturado); un único reintento pasado su ventana de 5 s
            # recupera la mayoría de los casos sin insistir.
            if response.status_code == 429:
                await asyncio.sleep(6)
                response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
