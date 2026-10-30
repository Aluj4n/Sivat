"""
Vista Búsqueda (SRS, sección 5): el periodista rastrea a mano noticias o temas
por palabras clave en lo que SIVAT ya tiene: el feed temporal (24 h) y el
historial de afirmaciones evaluadas.

La coincidencia ignora mayúsculas y tildes ("peru" encuentra "Perú") y cada
término vale como prefijo ("vacan" encuentra "vacancia"). Deben aparecer
todos los términos con contenido de la consulta.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence

from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from ml.limpieza_texto import STOPWORDS_ES, _quitar_tildes
from models.entities import Afirmacion, DecisionEditorial, EvaluacionIA, FuenteExterna, NoticiaFeed
from services.clasificador_service import clasificar_senal
from services.evidencia_service import titular_de
from services.normalizacion import PAISES_PERU, PANEL_PERU, serializar_feed

MAX_RESULTADOS = 30


def normalizar(texto: Optional[str]) -> str:
    return _quitar_tildes((texto or "").lower())


def terminos_de(consulta: str) -> List[str]:
    """Términos de la consulta sin palabras vacías; si solo hay vacías, se usan tal cual."""
    palabras = re.findall(r"\w+", normalizar(consulta))
    con_contenido = [p for p in palabras if p not in STOPWORDS_ES]
    return con_contenido or palabras


def _patrones(terminos: Sequence[str]) -> List[re.Pattern]:
    return [re.compile(rf"\b{re.escape(t)}") for t in terminos]


def coincide(texto: Optional[str], patrones: Sequence[re.Pattern]) -> bool:
    normal = normalizar(texto)
    return bool(patrones) and all(p.search(normal) for p in patrones)


def _orden(en_titular: bool, fecha: Optional[datetime]) -> tuple:
    # Primero lo que tiene todos los términos en el titular, luego lo más reciente
    marca = fecha.timestamp() if fecha else 0.0
    return (not en_titular, -marca)


async def buscar_noticias(db: AsyncSession, consulta: str, panel: Optional[str] = None) -> List[dict]:
    patrones = _patrones(terminos_de(consulta))
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    sentencia = select(NoticiaFeed).where(NoticiaFeed.fecha_captura >= limite)
    if panel:
        es_peru = func.lower(NoticiaFeed.pais).in_(PAISES_PERU)
        sentencia = sentencia.where(
            es_peru if panel == PANEL_PERU else or_(NoticiaFeed.pais.is_(None), not_(es_peru))
        )
    noticias = (await db.execute(sentencia)).scalars().all()

    halladas = [
        (coincide(n.titular, patrones), n) for n in noticias
        if coincide(f"{n.titular or ''} {n.texto_procesado or ''}", patrones)
    ]
    halladas.sort(key=lambda par: _orden(par[0], par[1].fecha_publicacion or par[1].fecha_captura))
    return [serializar_feed(n) for _, n in halladas[:MAX_RESULTADOS]]


async def historial_afirmaciones(db: AsyncSession) -> List[dict]:
    """
    Cada afirmación evaluada con su última evaluación, su fuente y su última
    decisión editorial.
    """
    filas = (await db.execute(
        select(EvaluacionIA, Afirmacion.contenido, FuenteExterna)
        .join(Afirmacion, EvaluacionIA.afirmacion_id == Afirmacion.id)
        .outerjoin(FuenteExterna, Afirmacion.fuente_id == FuenteExterna.id)
        .order_by(EvaluacionIA.fecha_evaluacion.desc())
    )).all()

    decisiones = (await db.execute(
        select(DecisionEditorial).order_by(DecisionEditorial.fecha_decision.desc())
    )).scalars().all()
    decision_por_afirmacion: dict[int, DecisionEditorial] = {}
    for decision in decisiones:
        decision_por_afirmacion.setdefault(decision.afirmacion_id, decision)

    historial, vistas = [], set()
    for evaluacion, contenido, fuente in filas:
        # Una afirmación reevaluada aparece una vez, con su evaluación más reciente
        if evaluacion.afirmacion_id in vistas:
            continue
        vistas.add(evaluacion.afirmacion_id)
        decision = decision_por_afirmacion.get(evaluacion.afirmacion_id)
        suficiente = len(contenido.split()) >= settings.MIN_PALABRAS_MODELO
        historial.append({
            "afirmacion_id": evaluacion.afirmacion_id,
            "titular": titular_de(contenido),
            "contenido": contenido,
            "fuente_origen": fuente.origen if fuente else None,
            "url_original": fuente.url_original if fuente else None,
            "fecha_evaluacion": evaluacion.fecha_evaluacion.isoformat() if evaluacion.fecha_evaluacion else None,
            "senal": (
                clasificar_senal(evaluacion.probabilidad_desinformacion) if suficiente
                else "Texto insuficiente para el modelo"
            ),
            "nivel_evidencia_disponible": evaluacion.nivel_evidencia_disponible,
            "decision": decision.decision_periodista if decision else None,
            "comentarios": decision.comentarios if decision else None,
            "fecha_decision": decision.fecha_decision.isoformat() if decision else None,
        })
    return historial


async def buscar_historial(db: AsyncSession, consulta: str) -> List[dict]:
    patrones = _patrones(terminos_de(consulta))
    halladas = [
        (coincide(r["titular"], patrones), r) for r in await historial_afirmaciones(db)
        if coincide(r["contenido"], patrones)
    ]
    # Ya vienen de la más reciente a la más antigua; sort es estable
    halladas.sort(key=lambda par: not par[0])
    # El texto completo solo sirve para buscar; no viaja al frontend
    return [{k: v for k, v in r.items() if k != "contenido"} for _, r in halladas[:MAX_RESULTADOS]]
