import asyncio
import os
import dotenv
dotenv.load_dotenv()
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_schema():
    db_url = os.getenv('DATABASE_URL')
    engine = create_async_engine(db_url, echo=False)
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            ORDER BY table_name, ordinal_position;
        """))
        rows = res.fetchall()
        
        tables = {}
        for table, col, dtype in rows:
            tables.setdefault(table, []).append(f"{col} ({dtype})")
            
        for t, cols in tables.items():
            print(f"Table: {t}")
            for c in cols:
                print(f"  - {c}")
            print()
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_schema())
