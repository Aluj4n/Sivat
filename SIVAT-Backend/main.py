import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from api import ingesta, internacionales
from db.session import async_session
from services.ingesta_service import INGESTORES_INTERNACIONALES, ingerir_gdelt_internacional

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
app.include_router(internacionales.router, prefix=f"{settings.API_V1_STR}/noticias", tags=["Noticias Internacionales"])

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de SIVAT"}


async def _ciclo_ingesta_internacional() -> None:
    """
    Sondea X y YouTube en segundo plano de forma continua para que cualquier
    rumor o noticia nueva llegue al panel Internacionales en tiempo real (vía
    SSE), sin depender de que alguien abra el panel o pulse "Actualizar".
    """
    while True:
        for ingerir in INGESTORES_INTERNACIONALES:
            try:
                async with async_session() as db:
                    nuevos = await ingerir(db)
                    if nuevos:
                        logger.info(f"[ingesta-internacional] {ingerir.__name__}: {nuevos} nuevas")
            except Exception:
                logger.warning(f"[ingesta-internacional] Fallo en {ingerir.__name__}", exc_info=True)
        await asyncio.sleep(settings.INTERVAL_INGESTA_INTERNACIONAL_SEGUNDOS)


async def _ciclo_ingesta_gdelt() -> None:
    """
    Sondea GDELT por separado y con menor frecuencia: es un servicio gratuito
    sin API key que bloquea la IP por tiempo prolongado si se le insiste
    cada minuto igual que a X/YouTube. Se puede desactivar por completo con
    GDELT_INGESTA_HABILITADA=false en .env mientras la IP esté bloqueada.
    """
    if not settings.GDELT_INGESTA_HABILITADA:
        logger.info("[ingesta-gdelt] Deshabilitado por configuración (GDELT_INGESTA_HABILITADA=false)")
        return
    while True:
        try:
            async with async_session() as db:
                nuevos = await ingerir_gdelt_internacional(db)
                if nuevos:
                    logger.info(f"[ingesta-gdelt] {nuevos} nuevas")
        except Exception:
            logger.warning("[ingesta-gdelt] Fallo en ingerir_gdelt_internacional", exc_info=True)
        await asyncio.sleep(settings.INTERVAL_INGESTA_GDELT_SEGUNDOS)


@app.on_event("startup")
async def iniciar_ingesta_automatica() -> None:
    app.state.tarea_ingesta_internacional = asyncio.create_task(_ciclo_ingesta_internacional())
    app.state.tarea_ingesta_gdelt = asyncio.create_task(_ciclo_ingesta_gdelt())


@app.on_event("shutdown")
async def detener_ingesta_automatica() -> None:
    for nombre in ("tarea_ingesta_internacional", "tarea_ingesta_gdelt"):
        tarea = getattr(app.state, nombre, None)
        if tarea:
            tarea.cancel()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
