# Primero: carga PyTorch antes que scikit-learn (en Windows falla al revés, ver ml/__init__.py)
import ml  # noqa: F401, I001

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api import busqueda, dashboard, ingesta, internacionales, tendencias, verificacion
from db.migraciones import aplicar_migraciones
from db.session import async_session, engine
from services.evidencia_service import ingerir_verificadores
from services.ingesta_service import (
    ingerir_bluesky_internacional,
    ingerir_gdelt_internacional,
    ingerir_reddit_internacional,
    ingerir_rss_medios,
    ingerir_youtube_internacional,
    limpiar_feed_vencido,
)
from services.tendencias_service import calcular_tendencias

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API de Ingesta y Verificación para SIVAT",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, change to frontend specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(ingesta.router, prefix=f"{settings.API_V1_STR}/ingesta", tags=["Ingesta de Datos"])
app.include_router(internacionales.router, prefix=f"{settings.API_V1_STR}/noticias", tags=["Noticias (paneles Perú e Internacionales)"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["Dashboard"])
app.include_router(tendencias.router, prefix=f"{settings.API_V1_STR}/tendencias", tags=["Tendencias"])
app.include_router(verificacion.router, prefix=f"{settings.API_V1_STR}/verificacion", tags=["Verificación"])
app.include_router(busqueda.router, prefix=f"{settings.API_V1_STR}/busqueda", tags=["Búsqueda"])
@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de SIVAT"}


async def _ciclo(nombre: str, tarea, intervalo_segundos: int) -> None:
    """
    Ejecuta `tarea(db)` cada `intervalo_segundos` para siempre. Un fallo (API
    caída, 429, cuota agotada) solo se registra y se reintenta en el próximo
    ciclo, sin detener las demás fuentes.
    """
    while True:
        try:
            async with async_session() as db:
                resultado = await tarea(db)
                if resultado:
                    logger.info(f"[{nombre}] {resultado} registros")
        except Exception:
            logger.warning(f"[{nombre}] Fallo en el ciclo", exc_info=True)
        await asyncio.sleep(intervalo_segundos)


CICLOS_SEGUNDO_PLANO = [
    # (nombre, tarea, intervalo, habilitado)
    ("ingesta-gdelt", ingerir_gdelt_internacional, settings.INTERVAL_INGESTA_GDELT_SEGUNDOS,
     settings.GDELT_INGESTA_HABILITADA),
    ("ingesta-youtube", ingerir_youtube_internacional, settings.INTERVAL_INGESTA_YOUTUBE_SEGUNDOS,
     settings.YOUTUBE_INGESTA_HABILITADA),
    ("ingesta-bluesky", ingerir_bluesky_internacional, settings.INTERVAL_INGESTA_BLUESKY_SEGUNDOS,
     settings.BLUESKY_INGESTA_HABILITADA),
    ("ingesta-reddit", ingerir_reddit_internacional, settings.INTERVAL_INGESTA_REDDIT_SEGUNDOS,
     settings.REDDIT_INGESTA_HABILITADA),
    ("ingesta-rss", ingerir_rss_medios, settings.INTERVAL_INGESTA_RSS_SEGUNDOS,
     settings.RSS_INGESTA_HABILITADA),
    ("ingesta-verificadores", ingerir_verificadores, settings.INTERVAL_INGESTA_VERIFICADORES_SEGUNDOS,
     settings.VERIFICADORES_INGESTA_HABILITADA),
    ("tendencias", calcular_tendencias, settings.INTERVAL_TENDENCIAS_SEGUNDOS, settings.TENDENCIAS_HABILITADAS),
    ("limpieza-feed", limpiar_feed_vencido, 3600, True),
]


@app.on_event("startup")
async def iniciar_ciclos() -> None:
    await aplicar_migraciones(engine)
    app.state.tareas_fondo = []
    for nombre, tarea, intervalo, habilitado in CICLOS_SEGUNDO_PLANO:
        if not habilitado:
            logger.info(f"[{nombre}] Deshabilitado por configuración")
            continue
        app.state.tareas_fondo.append(asyncio.create_task(_ciclo(nombre, tarea, intervalo)))


@app.on_event("shutdown")
async def detener_ciclos() -> None:
    for tarea in getattr(app.state, "tareas_fondo", []):
        tarea.cancel()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
