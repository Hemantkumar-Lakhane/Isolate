"""
db/seed/healthcare_seed.py
===========================
Generates synthetic patient engagement data.
Run: python db/seed/healthcare_seed.py
"""
 
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
 
random.seed(43)
 
CONDITIONS = ["Type 2 Diabetes", "Hypertension", "COPD", "Heart Disease", "Anxiety/Depression", "Obesity"]
CARE_COORDS = ["Dr. Sarah Lee", "Dr. Marcus Webb", "Nurse Aisha Patel", "Dr. Tom Reyes"]
 
def generate_patients(n=100):
    patients = []
    for i in range(n):
        is_high_risk = i % 5 == 0
        is_moderate = i % 3 == 0 and not is_high_risk
        
        adherence = random.uniform(0.2, 0.5) if is_high_risk else (random.uniform(0.5, 0.75) if is_moderate else random.uniform(0.75, 1.0))
        days_since_visit = random.randint(60, 180) if is_high_risk else (random.randint(30, 90) if is_moderate else random.randint(7, 45))
        no_shows_90d = random.randint(2, 5) if is_high_risk else (random.randint(1, 3) if is_moderate else 0)
        
        patients.append({
            "id": str(uuid.uuid4()),
            "mrn": f"MRN-{random.randint(100000, 999999)}",
            "first_name": random.choice(["James", "Maria", "Robert", "Linda", "William", "Barbara"]),
            "last_name": random.choice(["Smith", "Garcia", "Johnson", "Lee", "Williams", "Brown"]),
            "age": random.randint(35, 85),
            "primary_condition": random.choice(CONDITIONS),
            "care_coordinator": random.choice(CARE_COORDS),
            "insurance": random.choice(["Medicare", "Medicaid", "BCBS", "Aetna", "United"]),
            "adherence_score": round(adherence, 2),
            "days_since_last_visit": days_since_visit,
            "no_shows_90d": no_shows_90d,
            "active_medications": random.randint(1, 8),
            "last_lab_result": (datetime.utcnow() - timedelta(days=random.randint(30, 180))).strftime("%Y-%m-%d"),
            "next_appointment": (datetime.utcnow() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d") if not is_high_risk else None,
            "phone": f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
            "preferred_contact": random.choice(["phone", "sms", "email"]),
            "_risk_label": "high_risk" if is_high_risk else ("moderate_risk" if is_moderate else "stable"),
        })
    return patients
 
 
def generate_appointments(patients, n_per_patient=3):
    appts = []
    statuses = ["scheduled", "completed", "no_show", "cancelled"]
    for patient in patients:
        for _ in range(random.randint(1, n_per_patient)):
            days_offset = random.randint(-90, 30)
            is_future = days_offset > 0
            status = "scheduled" if is_future else random.choices(
                ["completed", "no_show", "cancelled"],
                weights=[70, 20, 10]
            )[0]
            if patient["_risk_label"] == "high_risk" and not is_future:
                status = random.choices(["completed", "no_show", "cancelled"], weights=[40, 45, 15])[0]
            
            appts.append({
                "id": str(uuid.uuid4()),
                "patient_id": patient["id"],
                "patient_name": f"{patient['first_name']} {patient['last_name']}",
                "care_coordinator": patient["care_coordinator"],
                "appointment_type": random.choice(["Follow-up", "Routine Check", "Lab Review", "Urgent"]),
                "date": (datetime.utcnow() + timedelta(days=days_offset)).strftime("%Y-%m-%d"),
                "status": status,
                "condition": patient["primary_condition"],
                "_patient_risk": patient["_risk_label"],
            })
    return appts
 
 
def main():
    out = Path("db/seed/data")
    out.mkdir(parents=True, exist_ok=True)
    patients = generate_patients(100)
    appointments = generate_appointments(patients)
    
    with open(out / "healthcare_patients.json", "w") as f:
        json.dump(patients, f, indent=2)
    with open(out / "healthcare_appointments.json", "w") as f:
        json.dump(appointments, f, indent=2)
    
    high = sum(1 for p in patients if p["_risk_label"] == "high_risk")
    mod = sum(1 for p in patients if p["_risk_label"] == "moderate_risk")
    print(f"✓ {len(patients)} patients → db/seed/data/healthcare_patients.json")
    print(f"  High risk: {high}  Moderate: {mod}  Stable: {len(patients)-high-mod}")
    print(f"✓ {len(appointments)} appointments → db/seed/data/healthcare_appointments.json")
 
 
if __name__ == "__main__":
    main()