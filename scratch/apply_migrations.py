import asyncio
import os
import dotenv
dotenv.load_dotenv()
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def apply_migrations():
    db_url = os.getenv('DATABASE_URL')
    engine = create_async_engine(db_url, echo=False)
    
    # Read 001_core.sql
    with open('db/migrations/001_core.sql', 'r', encoding='utf-8') as f:
        sql_001 = f.read()
        
    # Read 002_medical_tourism.sql
    with open('db/migrations/002_medical_tourism.sql', 'r', encoding='utf-8') as f:
        sql_002 = f.read()

    status_001 = 'FAILURE'
    status_002 = 'FAILURE'
    err_001 = None
    err_002 = None
    
    async with engine.connect() as conn:
        raw_conn = await conn.get_raw_connection()
        driver_conn = raw_conn.driver_connection
        
        # 1. Drop legacy pre-Supabase tables if present to prevent schema conflict
        legacy_tables = [
            "a2a_requests", "agent_run_records", "agent_runs", "budget_settings",
            "custom_tools", "email_queue", "escalations", "integration_credentials",
            "outcomes", "password_reset_tokens", "pattern_memory", "system_events",
            "tenants", "users", "workflow_definitions", "workflow_instances"
        ]
        drop_sql = f"DROP TABLE IF EXISTS {', '.join(legacy_tables)} CASCADE;"
        try:
            await driver_conn.execute(drop_sql)
            print("✓ Dropped legacy conflicting pre-Supabase tables.")
        except Exception as e:
            print(f"Notice on dropping legacy tables: {e}")

        # 2. Execute 001_core.sql
        try:
            await driver_conn.execute(sql_001)
            status_001 = 'SUCCESS'
        except Exception as e:
            err_001 = str(e)

        # 3. Execute 002_medical_tourism.sql
        try:
            await driver_conn.execute(sql_002)
            status_002 = 'SUCCESS'
        except Exception as e:
            err_002 = str(e)

    # 4. Verification phase
    async with engine.connect() as conn:
        # Tables created
        res_tables = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
        ))
        tables = [r[0] for r in res_tables.fetchall()]
        
        # RLS-enabled tables
        res_rls = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true ORDER BY tablename;"
        ))
        rls_tables = [r[0] for r in res_rls.fetchall()]
        
        # RLS policies created
        res_policies = await conn.execute(text(
            "SELECT tablename, policyname, roles, cmd FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname;"
        ))
        policies = [{'table': r[0], 'policy': r[1], 'roles': r[2], 'cmd': r[3]} for r in res_policies.fetchall()]

        # Foreign Keys
        res_fks = await conn.execute(text(
            "SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name "
            "FROM information_schema.table_constraints AS tc "
            "JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            "JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public' "
            "ORDER BY tc.table_name, kcu.column_name;"
        ))
        fks = [{'table': r[0], 'col': r[1], 'ref_table': r[2], 'ref_col': r[3]} for r in res_fks.fetchall()]

    await engine.dispose()
    
    print("\n=================== MIGRATION VERIFICATION REPORT ===================")
    print(f"MIGRATIONS: {'SUCCESS' if status_001 == 'SUCCESS' and status_002 == 'SUCCESS' else 'FAILURE'}")
    print(f"001_core.sql: {status_001}")
    if err_001: print(f"  Error 001: {err_001}")
    print(f"002_medical_tourism.sql: {status_002}")
    if err_002: print(f"  Error 002: {err_002}")
    
    print(f"\n[TABLES CREATED ({len(tables)})]")
    for t in tables:
        print(f"  - {t}")
        
    print(f"\n[RLS ENABLED TABLES ({len(rls_tables)})]")
    for r in rls_tables:
        print(f"  - {r}")
        
    print(f"\n[RLS POLICIES ({len(policies)})]")
    for p in policies:
        print(f"  - Table: {p['table']}, Policy: {p['policy']}")
        
    print(f"\n[FOREIGN KEYS & CONSTRAINTS ({len(fks)})]")
    for fk in fks:
        print(f"  - {fk['table']}.{fk['col']} -> {fk['ref_table']}.{fk['ref_col']}")
    print("=====================================================================")

if __name__ == "__main__":
    asyncio.run(apply_migrations())
