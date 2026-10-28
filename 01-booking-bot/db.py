"""Хранение записей в SQLite — не нужен отдельный сервер базы данных."""
import sqlite3

DB_PATH = "bookings.db"


def _conn():
    return sqlite3.connect(DB_PATH)


def init():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, name TEXT, phone TEXT,
                service TEXT, day TEXT, slot TEXT,
                UNIQUE(day, slot)
            )"""
        )


def busy_slots(day):
    with _conn() as c:
        return {r[0] for r in c.execute("SELECT slot FROM bookings WHERE day = ?", (day,))}


def add_booking(user_id, name, phone, service, day, slot):
    """Возвращает False, если слот уже занят (защита от двойной записи)."""
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO bookings (user_id, name, phone, service, day, slot) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, phone, service, day, slot),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def user_bookings(user_id):
    with _conn() as c:
        return c.execute(
            "SELECT id, day, slot, service FROM bookings WHERE user_id = ? AND day >= date('now', 'localtime') "
            "ORDER BY day, slot",
            (user_id,),
        ).fetchall()


def day_bookings(day):
    with _conn() as c:
        return c.execute(
            "SELECT slot, name, phone, service FROM bookings WHERE day = ? ORDER BY slot", (day,)
        ).fetchall()


def cancel_booking(b_id, user_id):
    with _conn() as c:
        row = c.execute(
            "SELECT day, slot FROM bookings WHERE id = ? AND user_id = ?", (b_id, user_id)
        ).fetchone()
        if row:
            c.execute("DELETE FROM bookings WHERE id = ?", (b_id,))
        return row
