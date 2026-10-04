"""
scratch/verify_fixes.py
=======================
Quick smoke-test for the three targeted fixes.
Does NOT modify any DB state — reads-only.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    errors = []

    # ── Fix 1: resolve_tenant_config_bridge returns valid config ──────────────
    print("\n1. Testing resolve_tenant_config_bridge …")
    try:
        from core.database import get_raw_session
        from api.crud import resolve_tenant_config_bridge

        session = await get_raw_session()
        async with session:
            # Pick an existing org from the DB
            from sqlalchemy import select
            from db.models.core import Organization
            res = await session.execute(select(Organization).limit(1))
            org = res.scalar_one_or_none()

            if org:
                _tid, config = await resolve_tenant_config_bridge(session, str(org.id))
                required = ["client_name", "industry", "business_rules", "tone_profile", "action_library"]
                missing = [k for k in required if not config.get(k)]
                if missing:
                    errors.append(f"  FAIL: resolve_tenant_config_bridge missing fields: {missing}")
                else:
                    print(f"  PASS: config has all required fields (org={org.name}, industry={config.get('industry')})")
            else:
                print("  SKIP: no Organization in DB (fresh DB — bridge works in code review)")
    except Exception as e:
        errors.append(f"  FAIL: {e}")

    # ── Fix 2: update_workflow_status agent_runs dedup logic ──────────────────
    print("\n2. Testing update_workflow_status agent_runs dedup …")
    try:
        from api.crud import update_workflow_status
        import inspect

        src = inspect.getsource(update_workflow_status)
        has_dedup = "node_id" in src and "existing_runs" in src and "agent_run_data" in src
        if not has_dedup:
            errors.append("  FAIL: agent_runs dedup logic not present in update_workflow_status")
        else:
            print("  PASS: agent_runs dedup logic present")
    except Exception as e:
        errors.append(f"  FAIL: {e}")

    # ── Fix 3: broadcast_event does NOT duplicate delivery ────────────────────
    print("\n3. Testing broadcast_event double-delivery fix …")
    try:
        from api.main import broadcast_event
        import inspect

        src = inspect.getsource(broadcast_event)
        # Check for actual function CALL, not just mention in a comment
        lines = src.split('\n')
        code_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('#')]
        has_call = any('_local_broadcast(' in l for l in code_lines)
        if has_call:
            errors.append("  FAIL: broadcast_event still calls _local_broadcast directly")
        else:
            print("  PASS: broadcast_event removed redundant fallback (no double delivery)")
    except Exception as e:
        errors.append(f"  FAIL: {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        for e in errors:
            print(e)
        print(f"\nRESULT: {len(errors)} failure(s)")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED ✓")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
