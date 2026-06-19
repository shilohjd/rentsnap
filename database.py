import sqlite3
import os

# Stores in the project root. Railway persists this between deploys
# as long as you're not on an ephemeral filesystem — we'll note this in README
DB_PATH = os.path.join(os.path.dirname(__file__), "rentsnap.db")


def init_db():
    """Create the counter table if it doesn't exist yet."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id    INTEGER PRIMARY KEY,
                key   TEXT UNIQUE,
                value INTEGER DEFAULT 0
            )
        """)
        # Seed the counter row so we can just UPDATE it later
        conn.execute("""
            INSERT OR IGNORE INTO stats (key, value)
            VALUES ('reports_generated', 0)
        """)
        conn.commit()


def increment_and_get() -> int:
    """Add 1 to the counter and return the new total."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE stats SET value = value + 1
            WHERE key = 'reports_generated'
        """)
        conn.commit()
        row = conn.execute("""
            SELECT value FROM stats WHERE key = 'reports_generated'
        """).fetchone()
    return row[0] if row else 1


def get_count() -> int:
    """Return current count without incrementing (used on the homepage)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("""
                SELECT value FROM stats WHERE key = 'reports_generated'
            """).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
