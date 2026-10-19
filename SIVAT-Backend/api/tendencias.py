import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from models.entities import NoticiaFeed, Tendencia
from services.normalizacion import PANEL_INTERNACIONAL, PANEL_PERU, serializar_feed

router = APIRouter()

ORDEN_PRIORIDAD = {"Alta": 0, "Media": 1, "Baja": 2}
HORAS_HISTORIAL = 24


def _serializar(tendencia: Tendencia, historial: list) -> dict:
    return {
        "id": tendencia.id,
        "grupo_id": tendencia.grupo_id,
        "panel": tendencia.panel,
        "terminos": tendencia.tema.split(", ") if tendencia.tema else [],
        "titular_representativo": tendencia.titular_representativo,
        "volumen": tendencia.volumen_menciones,
        "fuentes": tendencia.fuentes_distintas,
        "redes": tendencia.menciones_redes,
        "medios_reconocidos": tendencia.menciones_medios_reconocidos,
        "recientes": tendencia.recientes,
        "velocidad": tendencia.velocidad_crecimiento,
        "prioridad": tendencia.prioridad,
        "motivos": json.loads(tendencia.motivos or "[]"),
        "verificacion": json.loads(tendencia.verificacion) if tendencia.verificacion else None,
        "primera_vez": tendencia.primera_vez.isoformat(),
        "ejecucion": tendencia.ejecucion.isoformat(),
        # Volumen del tema en cada ciclo de las últimas 24 h (para ver si crece)
        "historial": historial,
    }


@router.get("")
async def obtener_tendencias(
    panel: str = Query(PANEL_INTERNACIONAL, pattern=f"^({PANEL_PERU}|{PANEL_INTERNACIONAL})$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Temas del último ciclo del panel, ordenados por prioridad de verificación
    (nunca por veracidad, RNF-08) y luego por publicaciones recientes.
    """
    ultima = await db.scalar(select(func.max(Tendencia.ejecucion)).where(Tendencia.panel == panel))
    if ultima is None:
        return {"ejecucion": None, "tendencias": []}
    resultado = await db.execute(select(Tendencia).where(Tendencia.panel == panel, Tendencia.ejecucion == ultima))
    tendencias = list(resultado.scalars().all())

    desde = ultima - timedelta(hours=HORAS_HISTORIAL)
    puntos = await db.execute(
        select(Tendencia.grupo_id, Tendencia.ejecucion, Tendencia.volumen_menciones)
        .where(Tendencia.grupo_id.in_([t.grupo_id for t in tendencias]), Tendencia.ejecucion >= desde)
        .order_by(Tendencia.ejecucion)
    )
    historial = defaultdict(list)
    for grupo_id, ejecucion, volumen in puntos.all():
        historial[grupo_id].append({"ejecucion": ejecucion.isoformat(), "volumen": volumen})

    tendencias.sort(key=lambda t: (ORDEN_PRIORIDAD.get(t.prioridad, 3), -t.recientes, -t.volumen_menciones))
    return {
        "ejecucion": ultima.isoformat(),
        "tendencias": [_serializar(t, historial[t.grupo_id]) for t in tendencias],
    }


@router.get("/{tendencia_id}/noticias")
async def noticias_de_tendencia(tendencia_id: int, db: AsyncSession = Depends(get_db)):
    """Las publicaciones del tema que siguen en el feed (lo vencido a las 24 h ya no está)."""
    tendencia = await db.get(Tendencia, tendencia_id)
    if tendencia is None:
        raise HTTPException(status_code=404, detail="La tendencia no existe")
    ids = json.loads(tendencia.noticia_ids or "[]")
    limite = datetime.now(timezone.utc) - timedelta(hours=settings.RETENCION_FEED_HORAS)
    resultado = await db.execute(
        select(NoticiaFeed)
        .where(NoticiaFeed.id.in_(ids), NoticiaFeed.fecha_captura >= limite)
        .order_by(NoticiaFeed.fecha_publicacion.desc().nullslast(), NoticiaFeed.id.desc())
    )
    return [serializar_feed(n) for n in resultado.scalars().all()]
