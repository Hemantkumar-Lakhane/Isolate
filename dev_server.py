"""
dev_server.py
=============
OpsGrid Development Data Server.

Serves realistic synthetic seed data over HTTP on port 8888.
Use as an alternative to direct file-reading tools when you need
a real HTTP endpoint (e.g., for testing GenericRESTConnector).

NOTE: The local_dev_tools.py approach (reading files directly) is preferred
for development. Use this server only if you specifically need HTTP endpoints.

Run: python dev_server.py
Then set in tenant config:
  "product_db": {
    "enabled": true,
    "base_url": "http://localhost:8888",
    "endpoints": {
      "usage": "/api/saas/accounts",
      "nps": "/api/saas/nps"
    }
  }
"""

from __future__ import annotations

import asyncio
import structlog
import httpx

log = structlog.get_logger()

@app.on_event("startup")
async def trigger_startup_demo():
    """Call the main API startup demo endpoint after server start, if enabled.

    Controlled by the environment variable ``ENABLE_STARTUP_DEMO``. In production
    or normal development runs this will be ``false`` (default) and the demo will
    not execute. This preserves idempotency and scoping – the endpoint itself
    also checks a lock file, but we avoid the network request entirely unless the
    developer explicitly opts in.
    """
    if os.getenv("ENABLE_STARTUP_DEMO", "false").lower() != "true":
        log.info("Startup demo disabled via ENABLE_STARTUP_DEMO flag")
        return
    # Wait briefly for the main API server to be up (if running locally on 8000)
    await asyncio.sleep(0.5)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("http://localhost:8000/internal/startup-demo")
            if resp.status_code == 200:
                log.info("Startup demo triggered", response=resp.json())
            else:
                log.warning("Startup demo request failed", status=resp.status_code, body=resp.text)
    except Exception as e:
        log.error("Failed to trigger startup demo", error=str(e))


SEED_DIR = Path("db/seed/data")

try:
    import uvicorn
    from fastapi import FastAPI, Query
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    print("Install fastapi and uvicorn: pip install fastapi uvicorn[standard]")
    sys.exit(1)

app = FastAPI(
    title="OpsGrid Dev Data Server",
    version="1.0.0",
    description="Serves synthetic seed data for local development. Does NOT represent real business data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load(filename: str) -> list:
    p = SEED_DIR / filename
    if p.exists():
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else []
    return []


# ─────────────────────────────────────────────────────────────────────────────
# SaaS Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/saas/accounts")
async def get_saas_accounts(
    account_id: Optional[str] = Query(None),
    health: Optional[str] = Query(None, description="critical | at_risk | healthy"),
    limit: int = Query(30, le=120),
):
    """SaaS customer accounts with usage metrics and churn signals."""
    accounts = _load("saas_accounts.json")
    if account_id:
        accounts = [a for a in accounts if a.get("id") == account_id]
    if health:
        accounts = [a for a in accounts if a.get("_health_label") == health]

    # Smart sampling
    if not account_id and not health:
        critical = [a for a in accounts if a.get("_health_label") == "critical"]
        at_risk  = [a for a in accounts if a.get("_health_label") == "at_risk"]
        healthy  = [a for a in accounts if a.get("_health_label") == "healthy"]
        accounts = (critical[:8] + at_risk[:12] + healthy[:5])[:limit]

    return {
        "accounts": accounts[:limit],
        "summary": {
            "total": len(_load("saas_accounts.json")),
            "returned": len(accounts[:limit]),
        },
    }


@app.get("/api/saas/nps")
async def get_saas_nps(
    score_below: Optional[int] = Query(None),
    limit: int = Query(50, le=120),
):
    """NPS scores and verbatim feedback."""
    accounts = _load("saas_accounts.json")
    nps_data = []
    for a in accounts:
        nps = a.get("nps", {})
        if not nps:
            continue
        score = nps.get("score", 7)
        if score_below is not None and score >= score_below:
            continue
        nps_data.append({
            "account_id": a.get("id"),
            "company_name": a.get("company_name"),
            "nps_score": score,
            "verbatim": nps.get("verbatim", ""),
            "date": nps.get("date", ""),
            "category": "promoter" if score >= 9 else ("passive" if score >= 7 else "detractor"),
        })
    return {"nps_data": nps_data[:limit], "total": len(nps_data)}


@app.get("/api/saas/deals")
async def get_saas_deals(
    stalled: Optional[bool] = Query(None),
    stage: Optional[str] = Query(None),
    limit: int = Query(30, le=80),
):
    """Sales pipeline deals."""
    deals = _load("saas_deals.json")
    if stalled is not None:
        deals = [d for d in deals if d.get("_stalled") == stalled]
    if stage:
        deals = [d for d in deals if d.get("stage") == stage]
    return {"deals": deals[:limit], "total": len(deals)}


# ─────────────────────────────────────────────────────────────────────────────
# Retail Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/retail/inventory")
async def get_retail_inventory(
    risk: Optional[str] = Query(None, description="stockout | overstock | healthy"),
    category: Optional[str] = Query(None),
    limit: int = Query(40, le=200),
):
    """Retail product inventory with risk indicators."""
    products = _load("retail_products.json")
    if risk:
        products = [p for p in products if p.get("_risk_label") == risk]
    if category:
        products = [p for p in products if p.get("category") == category]
    return {"products": products[:limit], "total": len(products)}


@app.get("/api/retail/sales")
async def get_retail_sales(limit: int = Query(30)):
    """Sales velocity data."""
    products = _load("retail_products.json")
    return {
        "sales_data": [
            {
                "product_id": p.get("id"),
                "sku": p.get("sku"),
                "name": p.get("name"),
                "units_sold_30d": p.get("sales_30d", 0),
                "days_of_supply": p.get("days_of_supply", 0),
                "sell_through_rate": p.get("sell_through_rate", 0),
            }
            for p in products[:limit]
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Healthcare Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health/patients")
async def get_patients(
    risk: Optional[str] = Query(None, description="high_risk | moderate_risk | stable"),
    limit: int = Query(30, le=200),
):
    """Patient records with risk indicators."""
    patients = _load("healthcare_patients.json")
    if risk:
        patients = [p for p in patients if p.get("_risk_label") == risk]
    return {"patients": patients[:limit], "total": len(patients)}


@app.get("/api/health/appointments")
async def get_appointments(
    status: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Appointment data."""
    appts = _load("healthcare_appointments.json")
    if status:
        appts = [a for a in appts if a.get("status") == status]
    if patient_id:
        appts = [a for a in appts if a.get("patient_id") == patient_id]
    return {"appointments": appts[:limit], "total": len(appts)}


# ─────────────────────────────────────────────────────────────────────────────
# Finance Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/finance/expenses")
async def get_expenses(
    department: Optional[str] = Query(None),
    anomaly_only: bool = Query(False),
    limit: int = Query(40, le=500),
):
    """Expense transactions with anomaly flags."""
    txns = _load("finance_expenses.json")
    if department:
        txns = [t for t in txns if t.get("department") == department]
    if anomaly_only:
        txns = [t for t in txns if t.get("_is_anomaly")]
    return {
        "transactions": txns[:limit],
        "summary": {
            "total": len(txns),
            "anomaly_count": len([t for t in txns if t.get("_is_anomaly")]),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    files = {f.name: f.stat().st_size for f in SEED_DIR.glob("*.json")} if SEED_DIR.exists() else {}
    return {
        "status": "ok",
        "server": "OpsGrid Dev Data Server",
        "seed_files": files,
        "endpoints": [
            "GET /api/saas/accounts",
            "GET /api/saas/nps",
            "GET /api/saas/deals",
            "GET /api/retail/inventory",
            "GET /api/retail/sales",
            "GET /api/health/patients",
            "GET /api/health/appointments",
            "GET /api/finance/expenses",
        ],
    }


if __name__ == "__main__":
    print("=" * 60)
    print("OpsGrid Dev Data Server")
    print("URL: http://localhost:8888")
    print("Docs: http://localhost:8888/docs")
    print("=" * 60)

    if not SEED_DIR.exists():
        print(f"\nWARNING: Seed data directory not found: {SEED_DIR}")
        print("Run seed scripts first:")
        print("  python db/seed/saas_seed.py")
        print("  python db/seed/retail_seed.py")
        print("  python db/seed/healthcare_seed.py")
        print("  python db/seed/finance_seed.py\n")

    uvicorn.run(app, host="0.0.0.0", port=8888, reload=True)