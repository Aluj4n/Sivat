"""
Cambios de esquema sobre tablas que ya existen: `create_all` solo crea tablas
nuevas, no agrega columnas. Cada sentencia es idempotente, así que se aplica
en cada arranque sin riesgo.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRACIONES = [
    # Conclusión del periodista al validar (flujo Validar / Observar / Descartar)
    "ALTER TABLE decision_editorial ADD COLUMN IF NOT EXISTS conclusion VARCHAR(50)",
    # 'Aceptado' del flujo anterior equivale a 'Validado'. 'Rechazado' no se
    # migra: esas afirmaciones vuelven a Pendientes para decidirlas de nuevo.
    "UPDATE decision_editorial SET decision_periodista = 'Validado' WHERE decision_periodista = 'Aceptado'",
]


async def aplicar_migraciones(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for sentencia in MIGRACIONES:
            await conn.execute(text(sentencia))
