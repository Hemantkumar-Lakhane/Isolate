"""
db/seed/saas_seed.py
====================
Generates realistic synthetic data for the SaaS Revenue Protection demo.

Produces:
  - 120 synthetic SaaS customer accounts
  - Usage metrics with churn signals baked in
  - HubSpot-style deal pipeline
  - NPS scores and support ticket history

Run: python db/seed/saas_seed.py
Output: db/seed/data/saas_accounts.json, saas_deals.json
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ── Realistic company names (fictional) ──────────────────────────────────────

COMPANY_PREFIXES = [
    "Apex", "Nova", "Bright", "Clear", "Swift", "Peak", "Bold", "Core",
    "Flux", "Mesh", "Grid", "Span", "Volt", "Wave", "Prism", "Nexus",
]
COMPANY_SUFFIXES = [
    "Solutions", "Systems", "Tech", "Works", "Labs", "HQ", "Cloud", "IO",
    "Analytics", "Platform", "Connect", "Ops", "Suite", "Desk", "Hub",
]
INDUSTRIES = [
    "Healthcare", "Finance", "Retail", "Logistics", "Manufacturing",
    "Real Estate", "Legal", "Marketing", "HR", "Education",
]
CSM_NAMES = [
    "Sarah Chen", "Marcus Webb", "Aisha Patel", "Derek Santos",
    "Julia Okafor", "Tom Reyes", "Priya Nair", "Jake Morrison",
]

random.seed(42)

def random_company() -> str:
    return f"{random.choice(COMPANY_PREFIXES)}{random.choice(COMPANY_SUFFIXES)}"

def random_email(company: str) -> str:
    domain = company.lower().replace(" ", "") + ".com"
    name = random.choice(["cto", "ops", "team", "admin", "success"])
    return f"{name}@{domain}"

def random_date_days_ago(min_days: int, max_days: int) -> str:
    days = random.randint(min_days, max_days)
    dt = datetime.utcnow() - timedelta(days=days)
    return dt.strftime("%Y-%m-%d")

def random_renewal_date() -> str:
    days = random.randint(14, 365)
    dt = datetime.utcnow() + timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def generate_accounts(n: int = 120) -> list[dict]:
    """Generate n realistic SaaS customer accounts with health signals."""
    accounts = []

    for i in range(n):
        company = random_company()
        tier = random.choices(["enterprise", "growth", "starter"], weights=[20, 40, 40])[0]
        mrr = {
            "enterprise": random.randint(3000, 15000),
            "growth": random.randint(800, 3000),
            "starter": random.randint(150, 800),
        }[tier]

        # Inject churn signals for ~30% of accounts
        is_at_risk = i % 3 == 0
        is_critical = i % 8 == 0

        base_dau = random.randint(10, 500)
        if is_critical:
            dau_trend = -random.uniform(0.4, 0.7)
        elif is_at_risk:
            dau_trend = -random.uniform(0.15, 0.4)
        else:
            dau_trend = random.uniform(-0.1, 0.3)

        current_dau = max(1, int(base_dau * (1 + dau_trend)))
        last_login_days = random.randint(1, 3)
        if is_critical:
            last_login_days = random.randint(15, 45)
        elif is_at_risk:
            last_login_days = random.randint(8, 20)

        support_tickets_30d = random.randint(0, 2)
        if is_critical:
            support_tickets_30d = random.randint(6, 20)
        elif is_at_risk:
            support_tickets_30d = random.randint(3, 8)

        nps_score = random.randint(7, 10)
        if is_critical:
            nps_score = random.randint(1, 4)
        elif is_at_risk:
            nps_score = random.randint(4, 7)

        accounts.append({
            "id": str(uuid.uuid4()),
            "company_name": company,
            "contact_email": random_email(company),
            "contact_name": f"{random.choice(['Alex','Jordan','Sam','Taylor','Morgan'])} "
                           f"{random.choice(['Kim','Park','Lee','Chen','Smith'])}",
            "csm_name": random.choice(CSM_NAMES),
            "tier": tier,
            "mrr": mrr,
            "industry": random.choice(INDUSTRIES),
            "renewal_date": random_renewal_date(),
            "contract_start": random_date_days_ago(180, 730),
            "usage": {
                "dau_30d_avg": base_dau,
                "dau_current": current_dau,
                "dau_trend_pct": round(dau_trend * 100, 1),
                "last_login_days_ago": last_login_days,
                "features_adopted": random.randint(2, 15),
                "features_available": 15,
                "session_duration_avg_min": random.randint(5, 60),
            },
            "support": {
                "open_tickets": random.randint(0, support_tickets_30d),
                "tickets_30d": support_tickets_30d,
                "avg_csat": round(random.uniform(2.5 if is_critical else 4.0, 5.0), 1),
                "last_ticket_days_ago": random.randint(0, 14) if support_tickets_30d > 0 else None,
            },
            "nps": {
                "score": nps_score,
                "date": random_date_days_ago(14, 90),
                "verbatim": _nps_verbatim(nps_score),
            },
            "stripe": {
                "subscription_status": "active" if not is_critical else random.choice(["active", "past_due"]),
                "payment_failures_90d": 0 if not is_critical else random.randint(0, 3),
                "next_billing": random_renewal_date(),
            },
            "_health_label": "critical" if is_critical else ("at_risk" if is_at_risk else "healthy"),
        })

    return accounts


def _nps_verbatim(score: int) -> str:
    if score >= 9:
        return random.choice([
            "Great product, saves us hours every week.",
            "The team loves it, easy to use.",
            "Exactly what we needed for our workflow.",
        ])
    if score >= 7:
        return random.choice([
            "Good but missing a few features we need.",
            "Decent product, could use better reporting.",
            "Works fine, not blown away.",
        ])
    if score >= 5:
        return random.choice([
            "Having trouble getting the team to adopt it.",
            "The interface is confusing for new users.",
            "Support response times are slow.",
        ])
    return random.choice([
        "Seriously considering switching to a competitor.",
        "Too many bugs, not reliable enough.",
        "Doesn't integrate well with our existing tools.",
    ])


def generate_deals(n: int = 80) -> list[dict]:
    """Generate open deals in pipeline."""
    stages = ["discovery", "demo", "proposal", "negotiation", "closing"]
    stage_weights = [30, 25, 20, 15, 10]

    deals = []
    for i in range(n):
        stage = random.choices(stages, weights=stage_weights)[0]
        stage_idx = stages.index(stage)
        days_in_stage = random.randint(1, 20)

        # 30% of deals are stalled beyond stage average
        is_stalled = random.random() < 0.30
        if is_stalled:
            stage_averages = {"discovery": 5, "demo": 7, "proposal": 10, "negotiation": 14, "closing": 7}
            days_in_stage = stage_averages[stage] + random.randint(3, 14)

        deals.append({
            "id": str(uuid.uuid4()),
            "company": random_company(),
            "contact": f"{'Alex Jordan Sam Taylor'.split()[i % 4]} {random.choice(['Williams','Brown','Davis'])}",
            "value": random.choice([5000, 10000, 25000, 50000, 75000, 100000, 150000]),
            "stage": stage,
            "days_in_stage": days_in_stage,
            "last_activity_days_ago": days_in_stage,
            "probability": {0: 10, 1: 25, 2: 45, 3: 70, 4: 85}[stage_idx],
            "close_date": random_renewal_date(),
            "owner": random.choice(CSM_NAMES),
            "industry": random.choice(INDUSTRIES),
            "notes": f"Last contact: {random.choice(['Email', 'Call', 'Meeting'])} {days_in_stage} days ago.",
            "_stalled": is_stalled,
        })

    return deals


def main():
    output_dir = Path("db/seed/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating SaaS demo data...")

    accounts = generate_accounts(120)
    with open(output_dir / "saas_accounts.json", "w") as f:
        json.dump(accounts, f, indent=2)
    print(f"  ✓ {len(accounts)} customer accounts → db/seed/data/saas_accounts.json")

    critical = sum(1 for a in accounts if a["_health_label"] == "critical")
    at_risk = sum(1 for a in accounts if a["_health_label"] == "at_risk")
    healthy = sum(1 for a in accounts if a["_health_label"] == "healthy")
    print(f"     Critical: {critical}  At-risk: {at_risk}  Healthy: {healthy}")

    deals = generate_deals(80)
    with open(output_dir / "saas_deals.json", "w") as f:
        json.dump(deals, f, indent=2)
    stalled = sum(1 for d in deals if d["_stalled"])
    print(f"  ✓ {len(deals)} pipeline deals → db/seed/data/saas_deals.json")
    print(f"     Stalled: {stalled}")

    print("\nSaaS seed data ready.")


if __name__ == "__main__":
    main()
