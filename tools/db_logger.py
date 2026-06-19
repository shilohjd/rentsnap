from langchain_core.tools import tool
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "dnh_intel.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT,
            address TEXT,
            bedrooms INTEGER,
            current_rent REAL,
            median_comp REAL,
            comp_low REAL,
            comp_high REAL,
            comp_count INTEGER,
            position TEXT,
            recommendation TEXT,
            run_date TEXT
        )
    """)
    conn.commit()
    conn.close()

@tool
def db_logger(unit_id: str, address: str, bedrooms: int, current_rent: float,
              median_comp: float, comp_low: float, comp_high: float,
              comp_count: int, position: str, recommendation: str) -> str:
    """Log a market snapshot for a unit to the database for historical tracking."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO market_snapshots
            (unit_id, address, bedrooms, current_rent, median_comp, comp_low,
             comp_high, comp_count, position, recommendation, run_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unit_id, address, bedrooms, current_rent,
            median_comp, comp_low, comp_high, comp_count,
            position, recommendation,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        conn.commit()
        conn.close()
        return f"Snapshot logged for {unit_id} on {datetime.now().strftime('%Y-%m-%d')}"
    except Exception as e:
        return f"Logging failed: {str(e)}"