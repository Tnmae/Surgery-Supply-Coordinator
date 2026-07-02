import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DATABASE_PATH = Path(__file__).parent / "medical_resources.db"

def setup_database():
    """Create SQLite database with multi-state schemas and seed data."""
    # Ensure directory exists
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 1. Hospitals Table (with state column)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            state TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    
    # 2. Blood Inventory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blood_inventory (
            id TEXT PRIMARY KEY,
            blood_type TEXT NOT NULL,
            unit_volume_ml INTEGER NOT NULL,
            status TEXT NOT NULL,
            crossmatch_status TEXT NOT NULL,
            collected_date TEXT NOT NULL,
            expiration_date TEXT NOT NULL,
            hospital_id TEXT NOT NULL,
            FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
        )
    """)
    
    # 3. Organ Registry Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organ_registry (
            id TEXT PRIMARY KEY,
            organ_type TEXT NOT NULL,
            donor_id TEXT NOT NULL,
            donor_blood_type TEXT NOT NULL,
            donor_age INTEGER NOT NULL,
            procurement_time TEXT NOT NULL,
            viability_window_minutes INTEGER NOT NULL,
            cold_storage_started TEXT NOT NULL,
            status TEXT NOT NULL,
            hospital_id TEXT NOT NULL,
            FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
        )
    """)
    
    # 4. Medicines Catalogue Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generic_name TEXT UNIQUE NOT NULL,
            brand_names TEXT NOT NULL,
            drug_class TEXT NOT NULL,
            indication TEXT,
            surgical_precautions TEXT NOT NULL,
            holding_period_days REAL NOT NULL,
            reverse_agent TEXT
        )
    """)
    
    # 5. Drug Interactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drug_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_a TEXT NOT NULL,
            drug_b TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    
    # 6. Surgical Equipment Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_inventory (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            status TEXT NOT NULL,
            sterilization_status TEXT NOT NULL,
            last_maintenance_date TEXT NOT NULL,
            next_maintenance_due TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            hospital_id TEXT NOT NULL,
            FOREIGN KEY (hospital_id) REFERENCES hospitals (id)
        )
    """)
    
    # 7. Medical Suppliers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medical_suppliers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_info TEXT NOT NULL,
            blood_types_supplied TEXT,
            organs_supplied TEXT,
            equipment_supplied TEXT,
            lead_time_hours INTEGER NOT NULL
        )
    """)
    
    # 8. Logistics / Vehicles Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logistics (
            id TEXT PRIMARY KEY,
            vehicle_type TEXT NOT NULL,
            status TEXT NOT NULL,
            base_hospital_id TEXT,
            destination_hospital_id TEXT,
            estimated_travel_time_minutes INTEGER,
            has_organ_preservation INTEGER NOT NULL DEFAULT 0,
            has_blood_cooler INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (base_hospital_id) REFERENCES hospitals (id),
            FOREIGN KEY (destination_hospital_id) REFERENCES hospitals (id)
        )
    """)
    
    conn.commit()
    
    # Clear existing tables to avoid duplicate entries
    cursor.execute("DELETE FROM logistics")
    cursor.execute("DELETE FROM medical_suppliers")
    cursor.execute("DELETE FROM equipment_inventory")
    cursor.execute("DELETE FROM drug_interactions")
    cursor.execute("DELETE FROM medicines")
    cursor.execute("DELETE FROM organ_registry")
    cursor.execute("DELETE FROM blood_inventory")
    cursor.execute("DELETE FROM hospitals")
    conn.commit()

    # Seed Multi-State Hospitals
    hospitals = [
        # New York (NY)
        ("HOSP-NY-01", "New York Presbyterian Hospital", "NY", "525 E 68th St, New York, NY", "212-746-5454", 40.7644, -73.9544),
        ("HOSP-NY-02", "Mount Sinai Hospital", "NY", "1468 Madison Ave, New York, NY", "212-241-6500", 40.7900, -73.9528),
        # California (CA)
        ("HOSP-CA-01", "Ronald Reagan UCLA Medical Center", "CA", "757 Westwood Plaza, Los Angeles, CA", "310-825-9111", 34.0672, -118.4482),
        ("HOSP-CA-02", "UCSF Helen Diller Medical Center", "CA", "505 Parnassus Ave, San Francisco, CA", "415-476-1000", 37.7631, -122.4578),
        # Texas (TX)
        ("HOSP-TX-01", "Houston Methodist Hospital", "TX", "6565 Fannin St, Houston, TX", "713-790-3311", 29.7118, -95.3978),
        ("HOSP-TX-02", "UT Southwestern Medical Center", "TX", "5323 Harry Hines Blvd, Dallas, TX", "214-648-3111", 32.8122, -96.8402),
        # Massachusetts (MA)
        ("HOSP-MA-01", "Massachusetts General Hospital", "MA", "55 Fruit St, Boston, MA", "617-726-2000", 42.3631, -71.0686)
    ]
    cursor.executemany("INSERT INTO hospitals VALUES (?, ?, ?, ?, ?, ?, ?)", hospitals)
    
    # Seed Blood Inventory
    now = datetime.utcnow()
    past_10_days = (now - timedelta(days=10)).isoformat()
    future_20_days = (now + timedelta(days=20)).isoformat()
    expired_2_days_ago = (now - timedelta(days=2)).isoformat()
    future_30_days = (now + timedelta(days=30)).isoformat()

    blood_units = [
        # NY Hospital units
        ("BLOOD-O-POS-01", "O+", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_20_days, "HOSP-NY-01"),
        ("BLOOD-O-POS-02", "O+", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_20_days, "HOSP-NY-01"),
        ("BLOOD-A-NEG-01", "A-", 450, "EXPIRED", "NOT_PERFORMED", past_10_days, expired_2_days_ago, "HOSP-NY-01"),
        ("BLOOD-AB-POS-01", "AB+", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_30_days, "HOSP-NY-01"),
        ("BLOOD-AB-POS-02", "AB+", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_30_days, "HOSP-NY-01"),
        
        # CA Hospital units
        ("BLOOD-O-NEG-01", "O-", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_20_days, "HOSP-CA-01"),
        ("BLOOD-B-POS-01", "B+", 450, "AVAILABLE", "NOT_PERFORMED", past_10_days, future_30_days, "HOSP-CA-01"),
        ("BLOOD-AB-NEG-01", "AB-", 450, "AVAILABLE", "NOT_PERFORMED", past_10_days, future_30_days, "HOSP-CA-02"),
        
        # TX Hospital units
        ("BLOOD-A-POS-01", "A+", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_20_days, "HOSP-TX-01"),
        ("BLOOD-O-POS-03", "O+", 450, "PENDING_CROSSMATCH", "PENDING", past_10_days, future_30_days, "HOSP-TX-02"),
        
        # MA Hospital units
        ("BLOOD-O-POS-04", "O+", 450, "AVAILABLE", "COMPATIBLE", past_10_days, future_20_days, "HOSP-MA-01")
    ]
    cursor.executemany("INSERT INTO blood_inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?)", blood_units)
    
    # Seed Organ Registry
    organ_procurement_1 = (now - timedelta(hours=1)).isoformat()
    organ_procurement_2 = (now - timedelta(hours=3)).isoformat()
    organ_procurement_3 = (now - timedelta(hours=6)).isoformat()

    organs = [
        # NY Heart
        ("ORGAN-HEART-NY", "HEART", "DONOR-5541", "O+", 25, organ_procurement_1, 240, organ_procurement_1, "AVAILABLE", "HOSP-NY-02"),
        # CA Liver
        ("ORGAN-LIVER-CA", "LIVER", "DONOR-7812", "B+", 40, organ_procurement_2, 480, organ_procurement_2, "AVAILABLE", "HOSP-CA-01"),
        # TX Kidney
        ("ORGAN-KIDNEY-TX", "KIDNEY", "DONOR-1092", "A+", 30, organ_procurement_3, 1440, organ_procurement_3, "AVAILABLE", "HOSP-TX-01")
    ]
    cursor.executemany("INSERT INTO organ_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", organs)
    
    # Seed Medicines Catalogue
    medicines = [
        ("WARFARIN", "Coumadin, Jantoven", "Anticoagulant", "Prevention of thrombosis, atrial fibrillation", "Critical bleeding risk. Hold 5 days prior to surgery. Validate pre-op INR is < 1.5.", 5.0, "Vitamin K, FFP"),
        ("ASPIRIN", "Ecotrin, Bayer Aspirin", "Antiplatelet / NSAID", "Analgesic, cardioprotection", "Moderate bleeding risk. Discontinue 7 days before major neurosurgical or high-risk cardiac procedures.", 7.0, "Platelet Transfusion"),
        ("METFORMIN", "Glucophage", "Oral Hypoglycemic", "Type 2 Diabetes mellitus", "Hold 24-48 hours prior to surgeries where hydration is restricted or contrast dye is injected.", 1.0, "Hemodialysis"),
        ("LISINOPRIL", "Zestril, Prinivil", "ACE Inhibitor", "Hypertension", "Hold the morning of surgery to prevent intraoperative refractory hypotension.", 1.0, "IV fluids, Vasopressors"),
        ("HEPARIN", "Hep-Lock", "Anticoagulant", "Thrombosis prevention", "Discontinue 4-6 hours before surgical procedures. Short half-life.", 0.25, "Protamine Sulfate"),
        ("CLOPIDOGREL", "Plavix", "Antiplatelet", "Prevention of stroke/MI", "Severe bleeding risk. Discontinue 5-7 days prior to major surgery.", 5.0, "Platelet Transfusion")
    ]
    cursor.executemany("INSERT INTO medicines (generic_name, brand_names, drug_class, indication, surgical_precautions, holding_period_days, reverse_agent) VALUES (?, ?, ?, ?, ?, ?, ?)", medicines)
    
    # Seed Drug Interactions
    interactions = [
        ("WARFARIN", "ASPIRIN", "CRITICAL", "Concurrent therapy severely increases hemorrhaging risks. High bleed hazard during incision."),
        ("HEPARIN", "WARFARIN", "HIGH", "Double anticoagulation. Bridge therapy protocol check required, otherwise extreme bleeding risk."),
        ("WARFARIN", "CLOPIDOGREL", "CRITICAL", "Severe risk of life-threatening gastrointestinal or surgical site bleeding.")
    ]
    cursor.executemany("INSERT INTO drug_interactions (drug_a, drug_b, severity, description) VALUES (?, ?, ?, ?)", interactions)
    
    # Seed Surgical Equipment across states
    equipment = [
        # NY
        ("EQ-VENT-NY", "VENTILATOR", "VENTILATOR", "AVAILABLE", "STERILE", "2026-06-15T10:00:00", "2026-07-15T10:00:00", "SN-VENT-101", "HOSP-NY-01"),
        ("EQ-MON-NY", "CARDIAC_MONITOR", "MONITOR", "AVAILABLE", "STERILE", "2026-06-20T10:00:00", "2026-07-20T10:00:00", "SN-MON-981", "HOSP-NY-01"),
        ("EQ-BYPASS-NY", "BYPASS_MACHINE", "CARDIAC_BYPASS", "AVAILABLE", "STERILE", "2026-06-10T10:00:00", "2026-07-10T10:00:00", "SN-BYPASS-04", "HOSP-NY-01"),
        
        # CA
        ("EQ-VENT-CA", "VENTILATOR", "VENTILATOR", "AVAILABLE", "STERILE", "2026-06-12T10:00:00", "2026-07-12T10:00:00", "SN-VENT-102", "HOSP-CA-01"),
        ("EQ-ANES-CA", "ANESTHESIA_MACHINE", "ANESTHESIA", "AVAILABLE", "STERILE", "2026-06-18T10:00:00", "2026-07-18T10:00:00", "SN-ANES-234", "HOSP-CA-01"),
        
        # TX
        ("EQ-VENT-TX-01", "VENTILATOR", "VENTILATOR", "AVAILABLE", "STERILE", "2026-06-22T08:00:00", "2026-07-22T08:00:00", "SN-VENT-201", "HOSP-TX-01"),
        ("EQ-VENT-TX-02", "VENTILATOR", "VENTILATOR", "UNDER_MAINTENANCE", "CONTAMINATED", "2026-05-15T10:00:00", "2026-06-15T10:00:00", "SN-VENT-202", "HOSP-TX-02")
    ]
    cursor.executemany("INSERT INTO equipment_inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", equipment)
    
    # Seed Medical Suppliers
    suppliers = [
        ("SUP001", "Alpha Medical Tech", "contact@alphamedical.com", None, None, "VENTILATOR,CARDIAC_MONITOR,BYPASS_MACHINE", 12),
        ("SUP002", "Global Blood Services", "logistics@globalblood.org", "O+,O-,A+,A-,B+,B-,AB+,AB-", None, None, 4),
        ("SUP003", "Regional Organ Logistics", "organs@regionaltransplant.org", None, "HEART,LIVER,KIDNEY", None, 6)
    ]
    cursor.executemany("INSERT INTO medical_suppliers VALUES (?, ?, ?, ?, ?, ?, ?)", suppliers)
    
    # Seed Logistics / Vehicles across states
    vehicles = [
        # NY vehicles
        ("VEH-AMB-NY", "AMBULANCE", "AVAILABLE", "HOSP-NY-01", None, 0, 0, 1),
        ("VEH-HELI-NY", "HELICOPTER", "AVAILABLE", "HOSP-NY-02", None, 0, 1, 1),
        
        # CA vehicles
        ("VEH-AMB-CA", "AMBULANCE", "AVAILABLE", "HOSP-CA-01", None, 0, 0, 1),
        ("VEH-HELI-CA", "HELICOPTER", "AVAILABLE", "HOSP-CA-02", None, 0, 1, 1),
        
        # TX vehicles
        ("VEH-AMB-TX", "AMBULANCE", "AVAILABLE", "HOSP-TX-01", None, 0, 1, 1)
    ]
    cursor.executemany("INSERT INTO logistics VALUES (?, ?, ?, ?, ?, ?, ?, ?)", vehicles)
    
    conn.commit()
    conn.close()
    print("Multi-state SQLite Medical Resources Database created and seeded successfully!")

if __name__ == "__main__":
    conn = sqlite3.connect(DATABASE_PATH)
    # Verify state column exists, if not drop table and rebuild
    try:
        conn.execute("SELECT state FROM hospitals LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("DROP TABLE IF EXISTS hospitals")
    conn.close()
    
    setup_database()
