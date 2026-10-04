"""
db/seed/finance_seed.py
========================
Generates synthetic corporate expense data with anomalies.
Run: python db/seed/finance_seed.py
"""
 
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
 
random.seed(44)
 
DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Operations", "Finance", "HR", "Executive"]
CATEGORIES = ["Travel", "Software", "Entertainment", "Office Supplies", "Training", "Meals", "Equipment"]
MANAGERS = {"Engineering": "CTO Mike Chen", "Sales": "VP Sales Lisa Park", "Marketing": "CMO Dave Reyes",
            "Operations": "COO Sarah Brown", "Finance": "CFO Tom Wilson", "HR": "CHRO Amy Lee", "Executive": "CEO"}
 
EXPENSE_LIMITS = {"Travel": 2000, "Software": 500, "Entertainment": 300, "Office Supplies": 200,
                  "Training": 1500, "Meals": 100, "Equipment": 1000}
 
def random_employee(dept):
    first = random.choice(["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Drew"])
    last = random.choice(["Kim", "Park", "Lee", "Chen", "Smith", "Johnson", "Williams", "Brown"])
    emp_id = f"EMP-{random.randint(1000, 9999)}"
    return {
        "id": emp_id,
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}@company.com",
        "department": dept,
        "manager": MANAGERS.get(dept, "Unknown"),
    }
 
def generate_expenses(n=300):
    transactions = []
    employees = {dept: [random_employee(dept) for _ in range(random.randint(3, 8))] for dept in DEPARTMENTS}
    
    for i in range(n):
        dept = random.choice(DEPARTMENTS)
        emp = random.choice(employees[dept])
        cat = random.choice(CATEGORIES)
        limit = EXPENSE_LIMITS.get(cat, 500)
        
        # Inject anomalies ~25% of transactions
        is_anomaly = (i % 4 == 0)
        if is_anomaly:
            amount = round(random.uniform(limit * 1.5, limit * 4), 2)
            anomaly_type = random.choice(["over_limit", "weekend_expense", "duplicate", "unusual_vendor"])
        else:
            amount = round(random.uniform(limit * 0.1, limit * 0.9), 2)
            anomaly_type = None
        
        days_ago = random.randint(0, 90)
        txn_date = datetime.utcnow() - timedelta(days=days_ago)
        is_weekend = txn_date.weekday() >= 5
        if is_weekend and not is_anomaly:
            is_anomaly = cat in ("Entertainment", "Travel")
            anomaly_type = "weekend_expense" if is_anomaly else anomaly_type
        
        transactions.append({
            "id": str(uuid.uuid4()),
            "employee_id": emp["id"],
            "employee_name": emp["name"],
            "employee_email": emp["email"],
            "department": dept,
            "manager": emp["manager"],
            "category": cat,
            "amount": amount,
            "currency": "USD",
            "date": txn_date.strftime("%Y-%m-%d"),
            "vendor": f"Vendor-{random.randint(1, 50)}",
            "description": f"{cat} expense for Q{(txn_date.month-1)//3+1}",
            "policy_limit": limit,
            "receipt_attached": random.random() > (0.3 if is_anomaly else 0.05),
            "approved": not is_anomaly or random.random() > 0.7,
            "_is_anomaly": is_anomaly,
            "_anomaly_type": anomaly_type,
        })
    
    return transactions
 
 
def main():
    out = Path("db/seed/data")
    out.mkdir(parents=True, exist_ok=True)
    transactions = generate_expenses(300)
    with open(out / "finance_expenses.json", "w") as f:
        json.dump(transactions, f, indent=2)
    
    anomalies = sum(1 for t in transactions if t["_is_anomaly"])
    total_amount = sum(t["amount"] for t in transactions)
    print(f"✓ {len(transactions)} expense transactions → db/seed/data/finance_expenses.json")
    print(f"  Anomalies: {anomalies}  Total amount: ${total_amount:,.2f}")
 
 
if __name__ == "__main__":
    main()