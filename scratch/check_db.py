import asyncio
from dotenv import load_dotenv
load_dotenv()

from core.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        for t in ['relationship_contacts', 'relationship_conversations', 'relationship_memory_items']:
            res = await conn.execute(text(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{t}'
                ORDER BY ordinal_position
            """))
            print(f"--- Table: {t} ---")
            for col in res.fetchall():
                print(f"  {col[0]}: {col[1]} (nullable={col[2]})")

if __name__ == '__main__':
    asyncio.run(check())
