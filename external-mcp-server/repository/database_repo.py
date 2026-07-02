import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

DATABASE_PATH = Path(__file__).parent.parent / "database" / "medical_resources.db"

logger = logging.getLogger("medical-repository")

class MedicalRepository:
    """Repository layer separating business logic from database interactions using SQLite."""
    
    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        
    def _get_connection(self) -> sqlite3.Connection:
        """Helper to get a database connection with dict factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===== Hospital queries =====
    def get_hospitals(self, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if search_query:
                    cursor.execute(
                        "SELECT * FROM hospitals WHERE name LIKE ? OR address LIKE ? OR state LIKE ?",
                        (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
                    )
                else:
                    cursor.execute("SELECT * FROM hospitals")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching hospitals: {str(e)}")
            return []

    # ===== Blood Inventory queries =====
    def get_blood_inventory(self, blood_type: str, hospital_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if hospital_id:
                    cursor.execute(
                        "SELECT * FROM blood_inventory WHERE blood_type = ? AND hospital_id = ?",
                        (blood_type, hospital_id)
                    )
                else:
                    cursor.execute("SELECT * FROM blood_inventory WHERE blood_type = ?", (blood_type,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching blood inventory: {str(e)}")
            return []

    # ===== Organ Registry queries =====
    def get_organs(self, organ_type: str, hospital_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if hospital_id:
                    cursor.execute(
                        "SELECT * FROM organ_registry WHERE organ_type = ? AND hospital_id = ?",
                        (organ_type, hospital_id)
                    )
                else:
                    cursor.execute("SELECT * FROM organ_registry WHERE organ_type = ?", (organ_type,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching organ registry: {str(e)}")
            return []

    # ===== Medicine Catalogue queries =====
    def get_medicines(self, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if search_query:
                    cursor.execute(
                        "SELECT * FROM medicines WHERE generic_name LIKE ? OR brand_names LIKE ? OR drug_class LIKE ?",
                        (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
                    )
                else:
                    cursor.execute("SELECT * FROM medicines")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching medicines: {str(e)}")
            return []

    # ===== Drug Interaction queries =====
    def get_interactions(self, drug_a: str, drug_b: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM drug_interactions 
                       WHERE (drug_a = ? AND drug_b = ?) OR (drug_a = ? AND drug_b = ?)""",
                    (drug_a.upper(), drug_b.upper(), drug_b.upper(), drug_a.upper())
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching drug interactions: {str(e)}")
            return None

    # ===== Equipment queries =====
    def get_equipment(self, name: Optional[str] = None, hospital_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM equipment_inventory WHERE 1=1"
                params = []
                if name:
                    query += " AND name = ?"
                    params.append(name.upper())
                if hospital_id:
                    query += " AND hospital_id = ?"
                    params.append(hospital_id)
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching equipment: {str(e)}")
            return []

    # ===== Suppliers queries =====
    def get_suppliers(self, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if search_query:
                    cursor.execute(
                        """SELECT * FROM medical_suppliers 
                           WHERE name LIKE ? OR blood_types_supplied LIKE ? 
                           OR organs_supplied LIKE ? OR equipment_supplied LIKE ?""",
                        (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
                    )
                else:
                    cursor.execute("SELECT * FROM medical_suppliers")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching suppliers: {str(e)}")
            return []

    # ===== Logistics queries =====
    def get_logistics_vehicles(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if status:
                    cursor.execute("SELECT * FROM logistics WHERE status = ?", (status,))
                else:
                    cursor.execute("SELECT * FROM logistics")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching logistics: {str(e)}")
            return []

    # ===== Storage Requirements queries =====
    def get_storage_requirements(self, resource_type: str, item_id: str) -> Optional[Dict[str, Any]]:
        try:
            # We derive storage requirements from the type and item metadata dynamically
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if resource_type.upper() == "BLOOD":
                    cursor.execute("SELECT * FROM blood_inventory WHERE id = ?", (item_id,))
                    row = cursor.fetchone()
                    if row:
                        return {
                            "item_id": item_id,
                            "type": "BLOOD_UNIT",
                            "storage_temperature_c": "2.0 to 6.0",
                            "requires_sterile_handling": True,
                            "transport_container": "Validated Blood Transit Bag",
                            "max_transit_duration_hours": 24
                        }
                elif resource_type.upper() == "ORGAN":
                    cursor.execute("SELECT * FROM organ_registry WHERE id = ?", (item_id,))
                    row = cursor.fetchone()
                    if row:
                        return {
                            "item_id": item_id,
                            "type": f"ORGAN_{row['organ_type']}",
                            "storage_temperature_c": "4.0 (Static Cold Storage)",
                            "requires_sterile_handling": True,
                            "transport_container": "Organ Preservation Transit Cooler",
                            "max_transit_duration_hours": f"Viability window limit: {row['viability_window_minutes']} minutes"
                        }
                elif resource_type.upper() == "EQUIPMENT":
                    cursor.execute("SELECT * FROM equipment_inventory WHERE id = ?", (item_id,))
                    row = cursor.fetchone()
                    if row:
                        return {
                            "item_id": item_id,
                            "type": f"EQUIPMENT_{row['name']}",
                            "storage_temperature_c": "Ambient room temperature",
                            "requires_sterile_handling": row['sterilization_status'] == 'STERILE',
                            "transport_container": "Protective Transit Cover",
                            "max_transit_duration_hours": "Indefinite (maintenance pending)"
                        }
            return None
        except Exception as e:
            logger.error(f"Error fetching storage requirements: {str(e)}")
            return None
