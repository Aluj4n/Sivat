"""
Módulo RAG de SIVAT (E2 del Acta de Alcance; Informe IA/ML): recupera
evidencia por similitud coseno sobre TF-IDF y la traduce en explicaciones
mediante reglas (sistema experto). Nunca emite un veredicto: las calificaciones
son de los verificadores y siempre se muestran atribuidas a ellos (RNF-08).
"""
import asyncio
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from ml.limpieza_texto import STOPWORDS_ES, _quitar_tildes, limpiar_texto
from models.entities import EvaluacionIA, EvidenciaAfirmacion, EvidenciaVerificacion, NoticiaFeed
from services.factcheck_service import GoogleFactCheckService
from services.normalizacion import _fecha_feed, _fecha_iso, _identificador, _recortar, _texto_plano
from services.rss_service import MEDIOS_RSS, RSSService

logger = logging.getLogger(__name__)

# Umbrales de similitud coseno (TF-IDF 1-2 gramas), calibrados con casos
# reales: lo no relacionado queda < 0.13 y otra cobertura del mismo hecho,
# redactada distinto, ronda 0.25. Las verificaciones usan un umbral
# menor porque reformulan la afirmación ("Es falso que...") y Google las
# devuelve con el título recortado.
UMBRAL_VERIFICACION = 0.15
UMBRAL_MEDIO = 0.20
MAX_POR_TIPO = 5
MAX_VERIFICACIONES_CORPUS = 5000

ORIGENES_SOCIALES = {"Bluesky", "Reddit", "YouTube", "X"}
MEDIOS_RECONOCIDOS = {medio for medio, _, _ in MEDIOS_RSS}
# Los mismos medios (y otros de referencia) cuando llegan vía GDELT con su dominio
DOMINIOS_RECONOCIDOS = {
    "bbc.com", "bbc.co.uk", "dw.com", "france24.com", "elpais.com", "infobae.com", "europapress.es",
    "euronews.com", "efe.com", "cnn.com", "apnews.com", "reuters.com", "rtve.es", "elmundo.es",
    "abc.es", "lavanguardia.com", "clarin.com", "lanacion.com.ar", "eltiempo.com", "elespectador.com",
    "emol.com", "latercera.com", "eluniversal.com.mx", "milenio.com", "elcomercio.com", "nytimes.com",
}


def es_medio_reconocido(origen: Optional[str]) -> bool:
    origen = (origen or "").lower().removeprefix("www.")
    return origen in {m.lower() for m in MEDIOS_RECONOCIDOS} or any(
        origen == d or origen.endswith("." + d) for d in DOMINIOS_RECONOCIDOS
    )


def _origen_medio(noticia: NoticiaFeed) -> str:
    # GDELT agrupa miles de medios: se muestra el dominio real del artículo
    if noticia.origen == "GDELT" and noticia.metadatos:
        try:
            return json.loads(noticia.metadatos).get("dominio") or noticia.origen
        except ValueError:
            pass
    return noticia.origen

# --- Calificación de los verificadores (reglas) ------------------------------

# El orden importa: "no es verdad" debe caer en Falso antes que en Verdadero
_REGLAS_CALIFICACION = [
    (re.compile(r"falta(?:n)? (?:de )?contexto|sin contexto|descontextualiz|fuera de contexto"), "Falta contexto"),
    (re.compile(r"enga[ñn]os[oa]"), "Engañoso"),
    (re.compile(r"impreciso|inexact|exagerad|parcialmente"), "Impreciso"),
    (re.compile(r"no es (?:verdad|cierto|real)|\bfals[oa]s?\b|\bbulo\b|\bfake\b|\bmentira\b|^no,"), "Falso"),
    (re.compile(r"\bverdader[oa]\b|\bes cierto\b|\bcorrecto\b"), "Verdadero"),
    (re.compile(r"\balerta\b"), "Alerta"),  # Maldita: aviso sobre contenido dañino o estafas
]
CALIFICACIONES_CONTRARIAS = {"Falso", "Engañoso", "Impreciso", "Falta contexto", "Alerta"}


def extraer_calificacion(*textos: Optional[str]) -> Optional[str]:
    for texto in textos:
        t = (texto or "").lower().strip()
        if not t:
            continue
        for patron, calificacion in _REGLAS_CALIFICACION:
            if patron.search(t):
                return calificacion
    return None


def normalizar_verificacion_rss(entrada: Dict[str, Any], verificador: str) -> Dict[str, Any]:
    titulo = html.unescape(entrada.get("title") or "").strip()
    url = entrada.get("link")
    # Solo etiquetas cortas tipo "Falso"; las largas son temas ("Alerta de género")
    etiquetas = [t.get("term") for t in entrada.get("tags") or [] if len((t.get("term") or "").split()) <= 2]
    # Solo el inicio del título ("Es falso que...", "Falta contexto:"); más
    # adelante "verdadero" o "falso" suelen ser parte del tema, no la calificación
    inicio = " ".join(titulo.split()[:3])
    return {
        "origen": verificador,
        "via": "rss",
        "identificador_externo": _identificador(url or entrada.get("id")),
        "titulo": _recortar(titulo, 500),
        "resumen": _texto_plano(entrada.get("summary"))[:2000],
        "calificacion": extraer_calificacion(inicio, *etiquetas),
        "url": _recortar(url, 1000),
        "fecha_publicacion": _fecha_feed(entrada),
    }


def normalizar_claim_google(claim: Dict[str, Any]) -> Dict[str, Any]:
    revision = (claim.get("claimReview") or [{}])[0]
    url = revision.get("url")
    rating = (revision.get("textualRating") or "").strip()
    # Sin "claimant": suele ser una persona y no aporta a la búsqueda (Ley 29733)
    return {
        "origen": _recortar((revision.get("publisher") or {}).get("name") or "Google Fact Check", 100),
        "via": "google_factcheck",
        "identificador_externo": _identificador(url or claim.get("text")),
        "titulo": _recortar(revision.get("title") or claim.get("text") or "", 500),
        "resumen": claim.get("text"),
        "calificacion": extraer_calificacion(rating) or _recortar(rating, 50) or None,
        "url": _recortar(url, 1000),
        "fecha_publicacion": _fecha_iso(revision.get("reviewDate") or claim.get("claimDate")),
    }


async def guardar_verificaciones(db: AsyncSession, registros: List[Dict[str, Any]]) -> int:
    unicos = {r["identificador_externo"]: r for r in registros if r.get("identificador_externo") and r.get("titulo")}
    if not unicos:
        return 0
    existentes = await db.execute(
        select(EvidenciaVerificacion.identificador_externo).where(
            EvidenciaVerificacion.identificador_externo.in_(list(unicos))
        )
    )
    ids_existentes = {fila[0] for fila in existentes.all()}
    nuevos = [EvidenciaVerificacion(**r) for i, r in unicos.items() if i not in ids_existentes]
    db.add_all(nuevos)
    await db.flush()
    return len(nuevos)


async def ingerir_verificadores(db: AsyncSession) -> int:
    data = await RSSService().fetch_verificadores()
    nuevos = await guardar_verificaciones(db, [normalizar_verificacion_rss(e, v) for e, v in data])
    await db.commit()
    return nuevos


# --- Recuperación (similitud coseno) -----------------------------------------

@dataclass
class Candidato:
    tipo: str  # 'verificacion' | 'medio'
    origen: str
    titulo: str
    url: Optional[str]
    calificacion: Optional[str]
    fecha_publicacion: Optional[datetime]
    texto: str


def titular_de(texto: str) -> str:
    """
    Primera línea con contenido: el titular cuando el texto es titular + cuerpo.
    El RAG compara afirmaciones, y con el artículo completo la similitud se diluye.
    """
    return next((linea.strip() for linea in texto.splitlines() if linea.strip()), "")[:500]


def consulta_factcheck(texto: str, max_palabras: int = 6) -> str:
    # Palabras con contenido del titular, en su forma original (con tildes)
    titular = texto.strip().split("\n")[0]
    palabras = [
        p for p in re.findall(r"\w+", titular)
        if len(p) > 2 and not p.isdigit() and _quitar_tildes(p.lower()) not in STOPWORDS_ES
    ]
    return " ".join(palabras[:max_palabras])


def rankear(texto: str, candidatos: List[Candidato]) -> List[Tuple[Candidato, float]]:
    consulta = limpiar_texto(texto)
    documentos = [limpiar_texto(c.texto) for c in candidatos]
    if not consulta or not candidatos:
        return []
    vectorizador = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    matriz = vectorizador.fit_transform([consulta] + documentos)
    similitudes = cosine_similarity(matriz[0], matriz[1:]).ravel()
    return sorted(zip(candidatos, similitudes), key=lambda par: par[1], reverse=True)


async def _buscar_en_google(db: AsyncSession, texto: str) -> None:
    # Si la consulta larga no trae nada, se prueba con menos palabras
    for max_palabras in (6, 4):
        consulta = consulta_factcheck(texto, max_palabras)
        if not consulta:
            return
        claims = await GoogleFactCheckService().search(consulta)
        if claims:
            await guardar_verificaciones(db, [normalizar_claim_google(c) for c in claims])
            return


async def _candidatos(db: AsyncSession, excluir_identificador: Optional[str]) -> List[Candidato]:
    verificaciones = await db.execute(
        select(EvidenciaVerificacion)
        .order_by(EvidenciaVerificacion.fecha_publicacion.desc().nullslast())
        .limit(MAX_VERIFICACIONES_CORPUS)
    )
    candidatos = [
        Candidato("verificacion", v.origen, v.titulo, v.url, v.calificacion, v.fecha_publicacion,
                  f"{v.titulo} {(v.resumen or '')[:300]}")
        for v in verificaciones.scalars().all()
    ]

    # Medios: lo publicado en las últimas 24 h por GDELT y RSS (no redes sociales)
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    consulta_medios = select(NoticiaFeed).where(
        NoticiaFeed.fecha_captura >= limite, NoticiaFeed.origen.not_in(ORIGENES_SOCIALES)
    )
    if excluir_identificador:
        consulta_medios = consulta_medios.where(NoticiaFeed.identificador_externo != excluir_identificador)
    medios = await db.execute(consulta_medios)
    candidatos += [
        Candidato("medio", _origen_medio(n), n.titular or "", n.url_original, None, n.fecha_publicacion,
                  f"{n.titular or ''} {(n.texto_procesado or '')[:300]}")
        for n in medios.scalars().all()
    ]
    return candidatos


def _seleccionar(ranking: List[Tuple[Candidato, float]], tipo: str, umbral: float) -> List[Tuple[Candidato, float]]:
    # Una verificación puede llegar por dos vías (RSS y Google) con URL distinta:
    # se compara también por el inicio del título. En medios no, porque dos
    # medios con el mismo titular son coberturas distintas.
    elegidos, vistos = [], set()
    for candidato, similitud in ranking:
        if candidato.tipo != tipo or similitud < umbral:
            continue
        claves = {candidato.url}
        if tipo == "verificacion":
            # 30 caracteres: Google recorta los títulos largos con "..."
            claves.add(limpiar_texto(candidato.titulo)[:30])
        claves -= {None, ""}
        if claves & vistos:
            continue
        vistos |= claves
        elegidos.append((candidato, similitud))
        if len(elegidos) == MAX_POR_TIPO:
            break
    return elegidos


async def buscar_y_guardar_evidencia(
    db: AsyncSession, evaluacion: EvaluacionIA, texto: str, excluir_identificador: Optional[str] = None
) -> List[EvidenciaAfirmacion]:
    """
    Busca evidencia para la afirmación de `evaluacion`, reemplaza la guardada
    (si se vuelve a buscar) y llena el desagregado de evidencia de la
    evaluación (Business Case 5.2). No hace commit.
    """
    try:
        await _buscar_en_google(db, texto)
    except Exception as e:
        # Sin Google se sigue con la base local de verificadores
        logger.warning(f"[evidencia] Google Fact Check no disponible: {e!r}")

    candidatos = await _candidatos(db, excluir_identificador)
    ranking = await asyncio.to_thread(rankear, texto, candidatos)
    elegidos = _seleccionar(ranking, "verificacion", UMBRAL_VERIFICACION) + _seleccionar(ranking, "medio", UMBRAL_MEDIO)

    await db.execute(delete(EvidenciaAfirmacion).where(EvidenciaAfirmacion.afirmacion_id == evaluacion.afirmacion_id))
    evidencias = [
        EvidenciaAfirmacion(
            afirmacion_id=evaluacion.afirmacion_id,
            tipo=c.tipo,
            origen=c.origen,
            titulo=_recortar(c.titulo, 500),
            url=c.url,
            calificacion=c.calificacion,
            similitud=round(float(s), 4),
            fecha_publicacion=c.fecha_publicacion,
        )
        for c, s in elegidos
    ]
    db.add_all(evidencias)

    _desagregar(evaluacion, evidencias)
    await db.flush()
    return evidencias


# --- Reglas: desagregado y explicación ---------------------------------------

def _desagregar(evaluacion: EvaluacionIA, evidencias: List[EvidenciaAfirmacion]) -> None:
    verificaciones = [e for e in evidencias if e.tipo == "verificacion"]
    medios = [e for e in evidencias if e.tipo == "medio"]
    calificadas = [e for e in verificaciones if e.calificacion in CALIFICACIONES_CONTRARIAS | {"Verdadero"}]

    evaluacion.fuentes_contradictorias = sum(e.calificacion in CALIFICACIONES_CONTRARIAS for e in verificaciones)
    evaluacion.fuentes_coincidentes = len(medios) + sum(e.calificacion == "Verdadero" for e in verificaciones)
    evaluacion.fuente_oficial_encontrada = any(es_medio_reconocido(e.origen) for e in medios)

    if calificadas or (evaluacion.fuente_oficial_encontrada and len(medios) >= 3):
        evaluacion.nivel_evidencia_disponible = "Alto"
    elif evidencias:
        evaluacion.nivel_evidencia_disponible = "Medio"
    else:
        evaluacion.nivel_evidencia_disponible = "Bajo"

    if verificaciones and medios:
        evaluacion.cobertura_evidencia = "Ambas"
    elif verificaciones:
        evaluacion.cobertura_evidencia = "Verificadores"
    elif medios:
        evaluacion.cobertura_evidencia = "Medios"
    else:
        evaluacion.cobertura_evidencia = "Ninguna"


def explicar(
    probabilidad: float,
    evidencias: List[EvidenciaAfirmacion],
    fuente_origen: Optional[str],
    texto_suficiente: bool = True,
) -> List[str]:
    """
    El "por qué" bajo el medidor (opción D). Cada razón describe evidencia o
    una señal; ninguna dice si la noticia es verdadera o falsa.
    """
    razones: List[str] = []
    verificaciones = [e for e in evidencias if e.tipo == "verificacion"]
    medios = [e for e in evidencias if e.tipo == "medio"]

    contrarias = [e for e in verificaciones if e.calificacion in CALIFICACIONES_CONTRARIAS]
    confirmadas = [e for e in verificaciones if e.calificacion == "Verdadero"]
    for e in contrarias[:2]:
        razones.append(f"{e.origen} calificó como «{e.calificacion}» una afirmación similar.")
    for e in confirmadas[:2]:
        razones.append(f"{e.origen} calificó como «Verdadero» una afirmación similar.")
    sin_calificar = len(verificaciones) - len(contrarias) - len(confirmadas)
    if sin_calificar and not (contrarias or confirmadas):
        razones.append(f"Hay {sin_calificar} verificación(es) sobre un tema similar, sin calificación explícita: revisar su contenido.")

    reconocidos = sorted({e.origen for e in medios if es_medio_reconocido(e.origen)})
    if reconocidos:
        razones.append(f"Medios reconocidos publicaron información similar: {', '.join(reconocidos)}.")
    elif medios:
        razones.append(f"{len(medios)} medio(s) del monitoreo publicaron información similar, ninguno de la lista de medios reconocidos.")

    if not evidencias:
        razones.append("No se encontró información similar en verificadores ni en los medios monitoreados: confirmar con una fuente primaria.")

    if fuente_origen in ORIGENES_SOCIALES:
        razones.append(f"Proviene de {fuente_origen} (red social): identificar la fuente primaria antes de difundir.")

    if not texto_suficiente:
        razones.append("El texto es muy corto para el modelo de redacción: decidir con la evidencia.")
    elif probabilidad >= 0.66:
        razones.append("La redacción tiene patrones frecuentes en textos de desinformación (modelo de texto).")
    elif probabilidad <= 0.33:
        razones.append("La redacción se parece a la de noticias confiables; esto no confirma los hechos.")
    else:
        razones.append("La redacción no muestra una señal clara en ningún sentido.")

    return razones
