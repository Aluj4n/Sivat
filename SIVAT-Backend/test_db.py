import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine

# Known fix for Windows Proactor loop issues with asyncpg
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test():
    engine = create_async_engine('postgresql+asyncpg://postgres:71502658@127.0.0.1:5432/sivat_db')
    try:
        async with engine.begin() as conn:
            print("CONNECTED SUCCESSFULLY")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == '__main__':
    asyncio.run(test())
