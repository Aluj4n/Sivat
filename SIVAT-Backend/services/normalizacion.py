import hashlib
import html
import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from models.entities import NoticiaFeed

PAISES_PERU = {"peru", "perú", "pe"}


def serializar_feed(noticia: "NoticiaFeed") -> Dict[str, Any]:
    """
    Formato común del endpoint REST del panel Internacionales y del stream SSE,
    para que el frontend trate igual ambas vías.
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
        "en_validacion": bool(noticia.en_validacion),
        "afirmacion_id": noticia.afirmacion_id,
    }


def es_noticia_peruana(registro: Dict[str, Any]) -> bool:
    return (registro.get("pais") or "").strip().lower() in PAISES_PERU


def _identificador(valor: Optional[str]) -> Optional[str]:
    # identificador_externo mide 255; algunas URLs de GDELT lo superan
    if valor and len(valor) > 255:
        return "sha256:" + hashlib.sha256(valor.encode("utf-8")).hexdigest()
    return valor


def _recortar(valor: Optional[str], largo: int) -> Optional[str]:
    return valor[:largo] if valor else valor


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
        "identificador_externo": _identificador(articulo.get("url") or articulo.get("url_mobile")),
        "titular": _recortar(articulo.get("title"), 500),
        "texto_procesado": articulo.get("title", ""),
        "imagen_url": _recortar(articulo.get("socialimage"), 1000),
        "url_original": _recortar(articulo.get("url"), 1000),
        "pais": pais,
        "fecha_publicacion": _parse_gdelt_fecha(articulo.get("seendate")),
        "metadatos": json.dumps(articulo, ensure_ascii=False),
    }


# El GKG no trae país de la fuente; se deduce del dominio (.pe → Perú, que se descarta)
PAIS_POR_DOMINIO = {
    "pe": "Peru", "mx": "Mexico", "ar": "Argentina", "es": "Spain", "co": "Colombia",
    "cl": "Chile", "ve": "Venezuela", "ec": "Ecuador", "bo": "Bolivia", "uy": "Uruguay",
    "py": "Paraguay", "do": "Dominican Republic", "cr": "Costa Rica", "gt": "Guatemala",
    "hn": "Honduras", "sv": "El Salvador", "ni": "Nicaragua", "pa": "Panama", "cu": "Cuba",
    "pr": "Puerto Rico",
}


def _pais_por_dominio(dominio: str, pais_default: str) -> str:
    sufijo = (dominio or "").rsplit(".", 1)[-1].lower()
    return PAIS_POR_DOMINIO.get(sufijo, pais_default)


def normalizar_gdelt_gkg(articulo: Dict[str, Any], pais_default: str = "INTL") -> Dict[str, Any]:
    # El GKG escapa los títulos como entidades HTML (p. ej. pa&#xED;s)
    titulo = html.unescape(articulo.get("titulo") or "").strip()
    return {
        "origen": "GDELT",
        "identificador_externo": _identificador(articulo.get("url")),
        "titular": _recortar(titulo, 500),
        "texto_procesado": titulo,
        "imagen_url": _recortar(articulo.get("imagen"), 1000),
        "url_original": _recortar(articulo.get("url"), 1000),
        "pais": _pais_por_dominio(articulo.get("dominio"), pais_default),
        "fecha_publicacion": _parse_gdelt_fecha(articulo.get("fecha")),
        "metadatos": json.dumps({"dominio": articulo.get("dominio"), "fuente": "gkg_15min"}, ensure_ascii=False),
    }


_RE_PERU = re.compile(r"\bper[uú]\b|\bperuan[oa]s?\b", re.IGNORECASE)
_RE_HTML = re.compile(r"<[^>]+>")


def _pais_salvo_peru(texto: str, pais: str) -> str:
    # Redes y RSS no traen país del contenido: si menciona Perú se marca para
    # que guardar_en_feed lo descarte (eso va al panel Perú, no a Internacionales)
    return "Peru" if _RE_PERU.search(texto or "") else pais


def _texto_plano(valor: Optional[str]) -> str:
    return html.unescape(_RE_HTML.sub(" ", valor or "")).split("submitted by")[0].strip()


def _fecha_iso(valor: Optional[str]) -> Optional[datetime]:
    if not valor:
        return None
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _fecha_feed(entrada: Dict[str, Any]) -> Optional[datetime]:
    # feedparser entrega las fechas ya normalizadas a UTC como struct_time
    struct = entrada.get("published_parsed") or entrada.get("updated_parsed")
    return datetime(*struct[:6], tzinfo=timezone.utc) if struct else None


def _imagen_feed(entrada: Dict[str, Any]) -> Optional[str]:
    for clave in ("media_thumbnail", "media_content"):
        for media in entrada.get(clave) or []:
            if media.get("url") and media.get("medium", "image") == "image":
                return media["url"]
    for enlace in entrada.get("links") or []:
        if (enlace.get("type") or "").startswith("image/"):
            return enlace.get("href")
    return None


def _imagen_bluesky(embed: Optional[Dict[str, Any]]) -> Optional[str]:
    if not embed:
        return None
    if embed.get("media"):  # recordWithMedia: cita + imágenes propias
        embed = embed["media"]
    if embed.get("images"):
        return embed["images"][0].get("thumb")
    return (embed.get("external") or {}).get("thumb")


def _enlace_bluesky(embed: Optional[Dict[str, Any]]) -> Optional[str]:
    # Noticia que comparte el post (tarjeta de enlace), también dentro de una cita
    if not embed:
        return None
    if embed.get("media"):
        embed = embed["media"]
    return (embed.get("external") or {}).get("uri")


def normalizar_bluesky(post: Dict[str, Any]) -> Dict[str, Any]:
    registro = post.get("record") or {}
    texto = (registro.get("text") or "").strip()
    uri = post.get("uri") or ""
    # at://<did>/app.bsky.feed.post/<rkey> -> enlace público; el DID es seudónimo
    partes = uri.removeprefix("at://").split("/")
    url = f"https://bsky.app/profile/{partes[0]}/post/{partes[-1]}" if len(partes) == 3 else None
    return {
        "origen": "Bluesky",
        "identificador_externo": _identificador(uri),
        "titular": _recortar(texto.replace("\n", " "), 500),
        "texto_procesado": texto,
        "imagen_url": _recortar(_imagen_bluesky(post.get("embed")), 1000),
        "url_original": url,
        "pais": _pais_salvo_peru(texto, "INTL"),
        "fecha_publicacion": _fecha_iso(registro.get("createdAt")),
        # Sin autor (Ley 29733); el alcance sirve luego para medir viralidad.
        # enlace_externo: la noticia compartida, para descargarla al validar
        "metadatos": json.dumps({
            "likes": post.get("likeCount"), "reposts": post.get("repostCount"), "respuestas": post.get("replyCount"),
            "enlace_externo": _enlace_bluesky(post.get("embed")),
        }),
    }


PAIS_POR_SUBREDDIT = {
    "argentina": "Argentina", "mexico": "Mexico", "chile": "Chile", "colombia": "Colombia",
    "vzla": "Venezuela", "es": "Spain", "uruguay": "Uruguay", "ecuador": "Ecuador",
}


_RE_ENLACE_REDDIT = re.compile(r'<a href="([^"]+)">\[link\]</a>')


def _enlace_reddit(entrada: Dict[str, Any]) -> Optional[str]:
    enlace = _RE_ENLACE_REDDIT.search(entrada.get("summary") or "")
    return html.unescape(enlace.group(1)) if enlace else None


def es_post_reddit_de_texto(entrada: Dict[str, Any]) -> bool:
    # El [link] de un post de solo texto apunta al propio hilo; los que enlazan
    # una noticia externa o una imagen/video son los que circulan como noticia
    enlace = _enlace_reddit(entrada)
    return not enlace or "reddit.com/r/" in enlace


def normalizar_reddit(entrada: Dict[str, Any]) -> Dict[str, Any]:
    titulo = html.unescape(entrada.get("title") or "").strip()
    subreddit = ((entrada.get("tags") or [{}])[0].get("term") or "").strip()
    cuerpo = _texto_plano(entrada.get("summary"))
    pais = PAIS_POR_SUBREDDIT.get(subreddit.lower(), "INTL")
    return {
        "origen": "Reddit",
        "identificador_externo": _identificador(entrada.get("id") or entrada.get("link")),
        "titular": _recortar(titulo, 500),
        "texto_procesado": f"{titulo}. {cuerpo}".strip(". ") if cuerpo else titulo,
        "imagen_url": _recortar(_imagen_feed(entrada), 1000),
        "url_original": _recortar(entrada.get("link"), 1000),
        "pais": _pais_salvo_peru(titulo, pais),
        "fecha_publicacion": _fecha_feed(entrada),
        # enlace_externo: la noticia compartida, para descargarla al validar
        "metadatos": json.dumps({"subreddit": subreddit, "enlace_externo": _enlace_reddit(entrada)}, ensure_ascii=False),
    }


def normalizar_rss(entrada: Dict[str, Any], medio: str, pais: str) -> Dict[str, Any]:
    titulo = html.unescape(entrada.get("title") or "").strip()
    resumen = _texto_plano(entrada.get("summary"))
    url = entrada.get("link")
    return {
        "origen": medio,
        "identificador_externo": _identificador(url or entrada.get("id")),
        "titular": _recortar(titulo, 500),
        "texto_procesado": f"{titulo}. {resumen}".strip(". ") if resumen else titulo,
        "imagen_url": _recortar(_imagen_feed(entrada), 1000),
        "url_original": _recortar(url, 1000),
        "pais": _pais_salvo_peru(f"{titulo} {url or ''}", pais),
        "fecha_publicacion": _fecha_feed(entrada),
        "metadatos": json.dumps({"medio": medio, "fuente": "rss"}, ensure_ascii=False),
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
        # La API de YouTube devuelve entidades HTML (p. ej. &#39;) en título y descripción
        "titular": _recortar(html.unescape(snippet.get("title") or ""), 500),
        "texto_procesado": html.unescape(snippet.get("description") or ""),
        "imagen_url": imagen,
        "url_original": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
        "pais": pais_default,
        "fecha_publicacion": fecha,
        "metadatos": json.dumps(item, ensure_ascii=False),
    }
