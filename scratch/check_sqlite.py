import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from db.models.core import Base as OrgBase

async def test_sqlite():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        try:
            await conn.run_sync(OrgBase.metadata.create_all)
            print("SQLite create_all succeeded!")
        except Exception as e:
            print("SQLite create_all error:", type(e), e)

if __name__ == '__main__':
    asyncio.run(test_sqlite())
