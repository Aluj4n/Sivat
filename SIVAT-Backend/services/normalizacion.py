import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from models.entities import FuenteExterna


def serializar_noticia(noticia: "FuenteExterna") -> Dict[str, Any]:
    """
    Formato común expuesto tanto por el endpoint REST de internacionales
    como por el stream en tiempo real (SSE), para que el frontend los trate igual.
    """
    return {
        "id": noticia.id,
        "titular": noticia.titular,
        "imagen_url": noticia.imagen_url,
        "url_original": noticia.url_original,
        "fuente_origen": noticia.origen,
        "pais": noticia.pais,
        "categoria": "INTERNACIONAL",
        "fecha_publicacion": noticia.fecha_publicacion.isoformat() if noticia.fecha_publicacion else None,
        # RESTRICCIÓN ÉTICA: nivel de confianza basado en transparencia/trazabilidad, NO un veredicto de veracidad
        "nivel_confianza": noticia.nivel_confianza_calculado,
    }


def _parse_gdelt_fecha(seendate: Optional[str]) -> Optional[datetime]:
    if not seendate:
        return None
    try:
        # GDELT formato: 'YYYYMMDDHHMMSS'
        return datetime.strptime(seendate, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalizar_gdelt(articulo: Dict[str, Any], pais_default: str = "INTL") -> Dict[str, Any]:
    pais = (articulo.get("sourcecountry") or pais_default).strip() or pais_default
    return {
        "origen": "GDELT",
        "identificador_externo": articulo.get("url") or articulo.get("url_mobile"),
        "titular": articulo.get("title"),
        "texto_procesado": articulo.get("title", ""),
        "imagen_url": articulo.get("socialimage"),
        "url_original": articulo.get("url"),
        "pais": pais,
        "fecha_publicacion": _parse_gdelt_fecha(articulo.get("seendate")),
        "metadatos": json.dumps(articulo, ensure_ascii=False),
    }


def normalizar_x(tweet: Dict[str, Any], pais_default: str = "INTL") -> Dict[str, Any]:
    texto = tweet.get("text", "")
    fecha = None
    if tweet.get("created_at"):
        try:
            fecha = datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00"))
        except ValueError:
            fecha = None
    return {
        "origen": "X",
        "identificador_externo": tweet.get("id"),
        "titular": texto[:140],
        "texto_procesado": texto,
        "imagen_url": None,
        "url_original": f"https://x.com/i/web/status/{tweet.get('id')}" if tweet.get("id") else None,
        "pais": pais_default,
        "fecha_publicacion": fecha,
        "metadatos": json.dumps(tweet, ensure_ascii=False),
    }


def normalizar_youtube(item: Dict[str, Any], pais_default: str = "INTL") -> Dict[str, Any]:
    snippet = item.get("snippet", {})
    video_id = (item.get("id") or {}).get("videoId")
    thumbnails = snippet.get("thumbnails", {})
    imagen = (thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}).get("url")
    fecha = None
    if snippet.get("publishedAt"):
        try:
            fecha = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        except ValueError:
            fecha = None
    return {
        "origen": "YouTube",
        "identificador_externo": video_id,
        "titular": snippet.get("title"),
        "texto_procesado": snippet.get("description", ""),
        "imagen_url": imagen,
        "url_original": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
        "pais": pais_default,
        "fecha_publicacion": fecha,
        "metadatos": json.dumps(item, ensure_ascii=False),
    }
