"""
db/seed/run_all_seeders.py
===========================
Run this ONCE before testing workflows in development.
Generates all seed data for all 4 industries.

Usage:
    python db/seed/run_all_seeders.py
    python db/seed/run_all_seeders.py --industry saas
    python db/seed/run_all_seeders.py --check    # just check what exists

Output: db/seed/data/*.json  (read by local_dev_tools.py at runtime)
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_seeder(module_path: str, name: str) -> bool:
    """Import and run a seeder module's main() function."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, module_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        if hasattr(mod, 'main'):
            mod.main()
        return True
    except Exception as e:
        print(f"  ✗ {name} failed: {e}")
        return False


def check_status() -> dict:
    """Return dict of {filename: exists} for all seed files."""
    data_dir = Path("db/seed/data")
    files = [
        "saas_accounts.json",
        "saas_deals.json",
        "retail_products.json",
        "healthcare_patients.json",
        "healthcare_appointments.json",
        "finance_expenses.json",
        "re_listings.json",
        "re_leases.json",
        "re_buyers.json",
        "email_messages.json",
        "campaign_orchestrator.json",
        "founder_content_requests.json",
        "product_launch_briefs.json",
        "weekly_growth_brief_data.json",
        "case_studies.json",
        "investor_updates.json",
        "pipeline_content_requests.json",
        "account_signals.json",
        "sla_monitor_events.json",
        "account_based_campaigns.json",
        "finance_operations.json",
    ]
    status = {}
    for fname in files:
        p = data_dir / fname
        if p.exists():
            try:
                data = json.loads(p.read_text())
                count = len(data) if isinstance(data, list) else "?"
                status[fname] = {"exists": True, "records": count, "kb": round(p.stat().st_size/1024, 1)}
            except Exception:
                status[fname] = {"exists": True, "records": "?"}
        else:
            status[fname] = {"exists": False, "records": 0}
    return status


def main():
    parser = argparse.ArgumentParser(description="OpsGrid Seed Data Generator")
    parser.add_argument("--industry", choices=["saas", "retail", "healthcare", "finance", "email"],
                        help="Generate data for specific industry or dataset only")
    parser.add_argument("--check", action="store_true", help="Check status without generating")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("OpsGrid Dev Seed Data Generator")
    print("=" * 60)

    if args.check:
        status = check_status()
        print("\nSeed Data Status:")
        for fname, info in status.items():
            icon = "[OK]" if info["exists"] else "[MISSING]"
            count_str = f"{info['records']} records  {info.get('kb', 0)} KB" if info["exists"] else "MISSING"
            print(f"  {icon:10s}  {fname:45s} {count_str}")
        missing = sum(1 for v in status.values() if not v["exists"])
        print(f"\n{'All data ready.' if missing == 0 else f'{missing} files missing. Run without --check to generate.'}")
        return

    seed_dir = Path("db/seed")
    seeders = {
        "saas":        seed_dir / "saas_seed.py",
        "retail":      seed_dir / "retail_seed.py",
        "healthcare":  seed_dir / "healthcare_seed.py",
        "finance":     seed_dir / "finance_seed.py",
        "real estate": seed_dir / "real_estate_seed.py",
        "email":       seed_dir / "email_seed.py",
    }

    to_run = {args.industry: seeders[args.industry]} if args.industry else seeders

    print(f"\nGenerating seed data for: {', '.join(to_run.keys())}")
    print()

    success = 0
    for industry, script in to_run.items():
        print(f"[{industry.upper()}]")
        if not script.exists():
            print(f"  ✗ Seeder not found: {script}")
            continue
        ok = run_seeder(str(script), industry)
        if ok:
            success += 1

    print("\n" + "-" * 60)
    status = check_status()
    for fname, info in status.items():
        icon = "✓" if info["exists"] else "✗"
        count_str = f"{info['records']} records" if info["exists"] else "MISSING"
        print(f"  {icon}  {fname:45s} {count_str}")

    print()
    if success == len(to_run):
        print("✅ All seed data ready. You can now trigger workflows.\n")
    else:
        print("⚠️  Some seeders failed. Check errors above.\n")

    # Run workflow scope seed (DB-level) if no specific industry filter
    if not args.industry:
        print("\n[WORKFLOW SCOPE SEED]")
        print("  Applying scope/industry to workflow_catalog in DB…")
        try:
            import asyncio as _asyncio
            scope_seed = seed_dir / "workflow_scope_seed.py"
            if scope_seed.exists():
                import importlib.util as _ilu
                spec = _ilu.spec_from_file_location("workflow_scope_seed", scope_seed)
                mod = _ilu.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _asyncio.run(mod.seed_workflow_scope(dry_run=False))
                print("  ✓ Workflow scope seed complete")
            else:
                print("  ✗ workflow_scope_seed.py not found")
        except Exception as e:
            print(f"  ⚠ Workflow scope seed failed (non-fatal): {e}")


if __name__ == "__main__":
    main()