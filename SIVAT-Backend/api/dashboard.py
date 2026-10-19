from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from models.entities import Afirmacion, DecisionEditorial, NoticiaFeed
from services.normalizacion import PANEL_INTERNACIONAL, PANEL_PERU, panel_de

router = APIRouter()

# Tipos de fuente del gráfico de ingesta; lo que no es una de estas es un medio por RSS
TIPOS_FUENTE = ["GDELT", "Medios RSS", "Bluesky", "Reddit", "YouTube"]
ORIGENES_PROPIOS = {"GDELT", "Bluesky", "Reddit", "YouTube", "X"}
DECISIONES = ["Aceptado", "Observado", "Rechazado"]


def _tipo_fuente(origen: str) -> str:
    return origen if origen in ORIGENES_PROPIOS else "Medios RSS"


@router.get("/resumen")
async def resumen(db: AsyncSession = Depends(get_db)):
    """
    Totales reales para el Dashboard: lo capturado en el feed (24 h) por tipo
    de fuente y panel, y el estado del flujo editorial de las afirmaciones.
    """
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    filas = await db.execute(
        select(NoticiaFeed.origen, NoticiaFeed.pais, func.count())
        .where(NoticiaFeed.fecha_captura >= limite)
        .group_by(NoticiaFeed.origen, NoticiaFeed.pais)
    )
    por_tipo = {tipo: {PANEL_PERU: 0, PANEL_INTERNACIONAL: 0} for tipo in TIPOS_FUENTE}
    for origen, pais, cantidad in filas.all():
        tipo = _tipo_fuente(origen)
        por_tipo.setdefault(tipo, {PANEL_PERU: 0, PANEL_INTERNACIONAL: 0})[panel_de(pais)] += cantidad
    por_panel = {panel: sum(v[panel] for v in por_tipo.values()) for panel in (PANEL_PERU, PANEL_INTERNACIONAL)}

    evaluadas = await db.scalar(select(func.count()).select_from(Afirmacion)) or 0
    # Cuenta la última decisión de cada afirmación (puede haber cambiado de opinión)
    decisiones = await db.execute(
        select(DecisionEditorial.afirmacion_id, DecisionEditorial.decision_periodista)
        .order_by(DecisionEditorial.afirmacion_id, DecisionEditorial.fecha_decision)
    )
    ultima = {afirmacion_id: decision for afirmacion_id, decision in decisiones.all()}
    conteo = Counter(ultima.values())

    return {
        "feed": {
            "horas": settings.RETENCION_FEED_HORAS,
            "total": sum(por_panel.values()),
            "por_panel": por_panel,
            "por_tipo": [{"tipo": tipo, **por_tipo[tipo]} for tipo in por_tipo],
        },
        "afirmaciones": {
            "evaluadas": evaluadas,
            "pendientes": max(evaluadas - len(ultima), 0),
            "decisiones": {decision: conteo.get(decision, 0) for decision in DECISIONES},
        },
    }
