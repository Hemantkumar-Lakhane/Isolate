"""
db/seed/retail_seed.py
=======================
Generates realistic synthetic retail inventory data.
Run: python db/seed/retail_seed.py
"""
 
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
 
random.seed(42)
 
CATEGORIES = ["Electronics", "Apparel", "Home & Garden", "Sports", "Beauty", "Food & Beverage", "Toys", "Office"]
BRANDS = ["ProTech", "StyleCo", "HomeBase", "ActiveGear", "GlowBeauty", "FreshFarm", "FunZone", "WorkSmart"]
BUYERS = ["Alice Chen", "Bob Martinez", "Carol Johnson", "Dave Patel", "Emma Wilson"]
 
def random_sku():
    return f"SKU-{random.randint(10000, 99999)}"
 
def generate_products(n=150):
    products = []
    for i in range(n):
        category = random.choice(CATEGORIES)
        brand = random.choice(BRANDS)
        base_stock = random.randint(0, 500)
        reorder_point = random.randint(20, 100)
        sales_30d = random.randint(5, 80)
        sales_7d = int(sales_30d * random.uniform(0.2, 0.3))
        days_of_supply = int(base_stock / max(sales_30d / 30, 0.1)) if base_stock > 0 else 0
        
        # Inject risk patterns
        is_stockout = i % 7 == 0 or base_stock < 10
        is_overstock = i % 9 == 0 or (base_stock > 400 and days_of_supply > 120)
        
        if is_stockout:
            base_stock = random.randint(0, 15)
            days_of_supply = random.randint(0, 5)
            risk = "stockout"
        elif is_overstock:
            base_stock = random.randint(350, 600)
            days_of_supply = random.randint(100, 200)
            risk = "overstock"
        else:
            risk = "healthy"
        
        sell_through = min(1.0, round(sales_30d / max(base_stock + sales_30d, 1), 2))
        
        products.append({
            "id": str(uuid.uuid4()),
            "sku": random_sku(),
            "name": f"{brand} {category} Product {i+1}",
            "brand": brand,
            "category": category,
            "current_stock": base_stock,
            "reorder_point": reorder_point,
            "reorder_quantity": reorder_point * 3,
            "sales_30d": sales_30d,
            "sales_7d": sales_7d,
            "sell_through_rate": sell_through,
            "days_of_supply": days_of_supply,
            "unit_cost": round(random.uniform(5, 200), 2),
            "unit_price": round(random.uniform(10, 400), 2),
            "supplier": f"Supplier-{random.randint(1, 20)}",
            "lead_time_days": random.randint(3, 21),
            "buyer": random.choice(BUYERS),
            "last_reorder_date": (datetime.utcnow() - timedelta(days=random.randint(7, 60))).strftime("%Y-%m-%d"),
            "_risk_label": risk,
        })
    
    return products
 
 
def main():
    out = Path("db/seed/data")
    out.mkdir(parents=True, exist_ok=True)
    products = generate_products(150)
    with open(out / "retail_products.json", "w") as f:
        json.dump(products, f, indent=2)
    
    stockout = sum(1 for p in products if p["_risk_label"] == "stockout")
    overstock = sum(1 for p in products if p["_risk_label"] == "overstock")
    print(f"✓ {len(products)} retail products → db/seed/data/retail_products.json")
    print(f"  Stockout risk: {stockout}  Overstock: {overstock}  Healthy: {len(products)-stockout-overstock}")
 
 
if __name__ == "__main__":
    main()