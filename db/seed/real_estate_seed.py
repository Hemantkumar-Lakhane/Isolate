"""
db/seed/real_estate_seed.py
============================
Generates synthetic real estate data for both brokerage and property management.

Produces:
  - 80 active MLS-style listings with showing feedback and comps
  - 60 tenant leases with payment history and maintenance tickets
  - 40 buyer leads

Run: python db/seed/real_estate_seed.py
Output: db/seed/data/re_listings.json, re_leases.json, re_buyers.json
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(77)

# ── Addresses ────────────────────────────────────────────────────────────────
STREETS = [
    "Oak Street", "Maple Avenue", "Cedar Lane", "Elm Drive", "Pine Court",
    "Willow Way", "Birch Boulevard", "Aspen Circle", "Walnut Road", "Cherry Path",
    "Sunset Boulevard", "Harbor View Drive", "Ridgeline Court", "Valley Road",
]
CITIES = ["Springfield", "Riverside", "Lakewood", "Hillcrest", "Mapleton"]
ZIP_CODES = ["73401", "73402", "73403", "73404", "73405"]
AGENTS = [
    "Sarah Chen", "Marcus Webb", "Lisa Park", "Derek Santos",
    "Priya Nair", "Tom Reyes", "Angela Brooks", "Jake Morrison",
]
PROPERTY_TYPES = ["Single Family", "Condo", "Townhouse", "Multi-Family"]
FEEDBACK_TYPES = ["showing", "open_house"]
NEGATIVE_FEEDBACK = [
    "Price seems high for the area",
    "Kitchen needs updating, not worth the asking price",
    "Priced above recent comps",
    "Needs too much work at this price point",
    "Buyer feels it's overpriced",
    "Better value available in the neighborhood",
]
POSITIVE_FEEDBACK = [
    "Great layout, very interested",
    "Loved the backyard, submitting offer",
    "Excellent condition for the price",
    "Perfect location, needs consideration",
]


def random_address():
    num = random.randint(100, 9999)
    street = random.choice(STREETS)
    city = random.choice(CITIES)
    state = "OK"
    zipcode = random.choice(ZIP_CODES)
    return f"{num} {street}", city, state, zipcode


def random_date_ago(min_days, max_days):
    d = datetime.utcnow() - timedelta(days=random.randint(min_days, max_days))
    return d.strftime("%Y-%m-%d")


def generate_listings(n=80):
    listings = []

    for i in range(n):
        street, city, state, zipcode = random_address()
        agent = random.choice(AGENTS)
        prop_type = random.choice(PROPERTY_TYPES)
        beds = random.randint(2, 5)
        baths = random.choice([1, 1.5, 2, 2.5, 3])
        sqft = random.randint(900, 3500)

        # Market pricing
        base_price_sqft = random.uniform(120, 280)
        orig_price = round(sqft * base_price_sqft / 1000) * 1000

        # Inject stale / price-reduced patterns
        is_stale = i % 5 == 0
        is_price_reduced = i % 4 == 0 and not is_stale

        dom = random.randint(3, 20)
        price_reductions = 0
        current_price = orig_price

        if is_stale:
            dom = random.randint(45, 180)
            price_reductions = random.randint(1, 4)
            current_price = round(orig_price * random.uniform(0.85, 0.97) / 1000) * 1000
        elif is_price_reduced:
            dom = random.randint(25, 60)
            price_reductions = random.randint(1, 2)
            current_price = round(orig_price * random.uniform(0.92, 0.98) / 1000) * 1000

        showing_count = max(0, int(random.gauss(dom * 0.8, 3)))
        if is_stale:
            showing_count = max(2, showing_count)

        # Generate showing feedback
        feedback = []
        neg_count = 0
        for _ in range(min(showing_count, 6)):
            has_price_concern = is_stale and random.random() > 0.4
            if has_price_concern:
                neg_count += 1
                feedback.append({
                    "type": random.choice(FEEDBACK_TYPES),
                    "comment": random.choice(NEGATIVE_FEEDBACK),
                    "date": random_date_ago(0, dom),
                    "price_concern": True,
                })
            elif random.random() > 0.6:
                feedback.append({
                    "type": random.choice(FEEDBACK_TYPES),
                    "comment": random.choice(POSITIVE_FEEDBACK),
                    "date": random_date_ago(0, dom),
                    "price_concern": False,
                })

        # Status
        if random.random() > 0.88:
            status = "pending"
        elif random.random() > 0.85:
            status = "sold"
        else:
            status = "active"

        # Risk label
        if status in ("pending", "sold"):
            risk = "healthy"
        elif is_stale and neg_count >= 2:
            risk = "stale"
        elif is_price_reduced:
            risk = "price_reduced"
        else:
            risk = "healthy"

        listings.append({
            "id": str(uuid.uuid4()),
            "address": street,
            "city": city,
            "state": state,
            "zip_code": zipcode,
            "property_type": prop_type,
            "bedrooms": beds,
            "bathrooms": baths,
            "sqft": sqft,
            "original_price": orig_price,
            "price": current_price,
            "price_per_sqft": round(current_price / sqft, 2),
            "price_reductions": price_reductions,
            "days_on_market": dom,
            "showing_count": showing_count,
            "negative_feedback_count": neg_count,
            "offers_received": random.randint(0, 3) if not is_stale else 0,
            "listing_agent": agent,
            "seller_email": f"seller{random.randint(100,999)}@example.com",
            "seller_name": f"{random.choice(['James','Maria','Robert','Linda'])} {random.choice(['Smith','Garcia','Johnson'])}",
            "list_date": random_date_ago(dom, dom + 2),
            "status": status,
            "showing_feedback": feedback,
            "_risk_label": risk,
        })

    return listings


# ── Leases ────────────────────────────────────────────────────────────────────
MAINTENANCE_ISSUES = [
    ("HVAC not cooling properly", "high"),
    ("Kitchen faucet leaking", "medium"),
    ("Garbage disposal broken", "medium"),
    ("Window seal cracked", "low"),
    ("Water heater making noise", "high"),
    ("Bathroom exhaust fan broken", "low"),
    ("Carpet stain from previous tenant", "low"),
    ("Ceiling water stain (possible leak)", "emergency"),
    ("Front door lock stiff", "medium"),
    ("Dishwasher not draining", "medium"),
]

TENANT_FIRST = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Drew"]
TENANT_LAST = ["Kim", "Park", "Lee", "Chen", "Smith", "Johnson", "Williams", "Brown"]


def generate_leases(n=60):
    leases = []
    for i in range(n):
        tenant_first = random.choice(TENANT_FIRST)
        tenant_last = random.choice(TENANT_LAST)
        tenant_name = f"{tenant_first} {tenant_last}"
        tenant_email = f"{tenant_first.lower()}.{tenant_last.lower()}{random.randint(1,99)}@email.com"

        # Lease timeline
        lease_start = datetime.utcnow() - timedelta(days=random.randint(180, 730))
        days_remaining = random.randint(-30, 400)
        lease_end = datetime.utcnow() + timedelta(days=days_remaining)

        monthly_rent = random.choice([850, 950, 1050, 1150, 1250, 1350, 1500, 1750, 2000])
        market_rent = round(monthly_rent * random.uniform(0.95, 1.20), -1)

        # Risk flags
        is_high_risk = i % 5 == 0
        is_medium_risk = i % 3 == 0 and not is_high_risk
        expiring_soon = days_remaining <= 90

        # Payment history
        payment_history = []
        months_tenanted = max(1, (datetime.utcnow() - lease_start).days // 30)
        for m in range(min(months_tenanted, 12)):
            due = lease_start + timedelta(days=m * 30 + 1)
            if is_high_risk:
                days_late = random.choices([0, 5, 12, 20, 0], weights=[40, 20, 20, 10, 10])[0]
            elif is_medium_risk:
                days_late = random.choices([0, 3, 7, 0], weights=[60, 20, 10, 10])[0]
            else:
                days_late = 0

            paid = due + timedelta(days=days_late)
            payment_history.append({
                "month": due.strftime("%Y-%m"),
                "amount": monthly_rent,
                "due_date": due.strftime("%Y-%m-%d"),
                "paid_date": paid.strftime("%Y-%m-%d"),
                "days_late": days_late,
                "status": "paid" if days_late == 0 else "paid_late",
            })

        # Maintenance tickets
        ticket_count = random.randint(4, 8) if is_high_risk else random.randint(0, 3)
        tickets = []
        for _ in range(ticket_count):
            issue, priority = random.choice(MAINTENANCE_ISSUES)
            ticket_date = random_date_ago(5, 180)
            is_resolved = not is_high_risk or random.random() > 0.5
            tickets.append({
                "id": str(uuid.uuid4())[:8],
                "issue": issue,
                "priority": priority,
                "submitted_date": ticket_date,
                "status": "resolved" if is_resolved else random.choice(["open", "in_progress"]),
                "days_open": 0 if is_resolved else random.randint(3, 45),
            })

        late_payments = [p for p in payment_history if p["days_late"] > 0]
        unresolved_tickets = [t for t in tickets if t["status"] in ("open", "in_progress")]

        # Risk score
        risk_score = 0
        if expiring_soon:
            risk_score += 30
        risk_score += len(late_payments) * 10
        risk_score += len(unresolved_tickets) * 8
        if market_rent > monthly_rent * 1.10:
            risk_score += 20  # strong incentive to move

        if risk_score >= 50 or (is_high_risk and expiring_soon):
            risk_label = "high_flight_risk"
        elif risk_score >= 25 or is_medium_risk:
            risk_label = "medium_flight_risk"
        else:
            risk_label = "stable"

        street, city, state, zipcode = random_address()
        leases.append({
            "id": str(uuid.uuid4()),
            "tenant_name": tenant_name,
            "tenant_email": tenant_email,
            "tenant_phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
            "property_id": str(uuid.uuid4())[:8],
            "property_address": street,
            "city": city,
            "state": state,
            "lease_start_date": lease_start.strftime("%Y-%m-%d"),
            "lease_end_date": lease_end.strftime("%Y-%m-%d"),
            "days_until_expiry": days_remaining,
            "monthly_rent": monthly_rent,
            "market_rent": market_rent,
            "rent_vs_market_delta": round(market_rent - monthly_rent, 2),
            "payment_history": payment_history,
            "late_payment_count": len(late_payments),
            "maintenance_tickets": tickets,
            "unresolved_ticket_count": len(unresolved_tickets),
            "risk_score": risk_score,
            "property_manager": random.choice(AGENTS),
            "renewal_offered": days_remaining <= 90 and random.random() > 0.5,
            "_risk_label": risk_label,
        })

    return leases


# ── Buyers ────────────────────────────────────────────────────────────────────

def generate_buyers(n=40):
    buyers = []
    for i in range(n):
        first = random.choice(TENANT_FIRST)
        last = random.choice(TENANT_LAST)
        price_min = random.choice([150000, 200000, 250000, 300000, 350000, 400000])
        price_max = price_min + random.choice([50000, 75000, 100000, 150000])
        beds_min = random.randint(2, 4)

        status = random.choice(["hot", "hot", "warm", "warm", "cold"])
        days_since_last_contact = random.randint(0, 60)

        buyers.append({
            "id": str(uuid.uuid4()),
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@email.com",
            "phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
            "assigned_agent": random.choice(AGENTS),
            "price_min": price_min,
            "price_max": price_max,
            "bedrooms_min": beds_min,
            "preferred_zip": random.choice(ZIP_CODES),
            "pre_approved": random.random() > 0.4,
            "pre_approval_amount": price_max if random.random() > 0.5 else None,
            "status": status,
            "days_since_last_contact": days_since_last_contact,
            "showings_attended": random.randint(0, 12),
            "created_date": random_date_ago(7, 180),
        })
    return buyers


def main():
    out = Path("db/seed/data")
    out.mkdir(parents=True, exist_ok=True)

    listings = generate_listings(80)
    leases = generate_leases(60)
    buyers = generate_buyers(40)

    with open(out / "re_listings.json", "w") as f:
        json.dump(listings, f, indent=2)
    with open(out / "re_leases.json", "w") as f:
        json.dump(leases, f, indent=2)
    with open(out / "re_buyers.json", "w") as f:
        json.dump(buyers, f, indent=2)

    stale = sum(1 for l in listings if l["_risk_label"] == "stale")
    pr = sum(1 for l in listings if l["_risk_label"] == "price_reduced")
    high_risk = sum(1 for l in leases if l["_risk_label"] == "high_flight_risk")

    print(f"✓ {len(listings)} listings → db/seed/data/re_listings.json")
    print(f"  Stale: {stale}  Price-reduced: {pr}  Healthy: {len(listings)-stale-pr}")
    print(f"✓ {len(leases)} leases → db/seed/data/re_leases.json")
    print(f"  High flight risk: {high_risk}")
    print(f"✓ {len(buyers)} buyers → db/seed/data/re_buyers.json")


if __name__ == "__main__":
    main()