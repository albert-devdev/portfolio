"""История цен в SQLite: каждый запуск сохраняет снимок, следующий сравнивает с ним."""
import sqlite3
from datetime import datetime

DB_PATH = "prices.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS snapshots (run_at TEXT, url TEXT, title TEXT, price REAL)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_run ON snapshots(run_at)")
    return c


def last_prices():
    """Цены из последнего запуска: {url: price}."""
    c = _conn()
    try:
        row = c.execute("SELECT MAX(run_at) FROM snapshots").fetchone()
        if not row[0]:
            return {}
        return dict(c.execute("SELECT url, price FROM snapshots WHERE run_at = ?", (row[0],)))
    finally:
        c.close()


def save(items):
    run_at = datetime.now().isoformat(timespec="seconds")
    c = _conn()
    try:
        c.executemany("INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                      [(run_at, it["url"], it["title"], it["price"]) for it in items])
        c.commit()
    finally:
        c.close()
