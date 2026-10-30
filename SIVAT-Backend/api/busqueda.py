from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.busqueda_service import buscar_historial, buscar_noticias, terminos_de
from services.normalizacion import PANEL_INTERNACIONAL, PANEL_PERU

router = APIRouter()


@router.get("")
async def buscar(
    q: str = Query(..., min_length=2, max_length=200, description="Palabras clave"),
    panel: Optional[str] = Query(None, pattern=f"^({PANEL_PERU}|{PANEL_INTERNACIONAL})$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Búsqueda manual por palabras clave en el feed de las últimas 24 h y en el
    historial de afirmaciones evaluadas con su decisión.
    """
    consulta = q.strip()
    if not terminos_de(consulta):
        raise HTTPException(status_code=422, detail="Escribe al menos una palabra para buscar.")

    return {
        "consulta": consulta,
        "noticias": await buscar_noticias(db, consulta, panel),
        "historial": await buscar_historial(db, consulta),
    }
