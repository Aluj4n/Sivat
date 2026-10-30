import asyncio
from db.migraciones import aplicar_migraciones
from db.session import engine
from models.base import Base
# Import all entities to ensure they are registered with Base before creating tables
from models.entities import FuenteExterna, Tendencia, Afirmacion, DecisionEditorial

async def init_models():
    async with engine.begin() as conn:
        # Create all tables in the database
        print("Creando tablas en la base de datos...")
        await conn.run_sync(Base.metadata.create_all)
        print("¡Tablas creadas exitosamente!")
    await aplicar_migraciones(engine)

if __name__ == "__main__":
    asyncio.run(init_models())
