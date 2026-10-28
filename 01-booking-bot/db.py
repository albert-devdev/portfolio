"""Хранение данных в SQLite — не нужен отдельный сервер базы данных."""
import sqlite3
from contextlib import contextmanager

DB_PATH = "bookings.db"
FLAGS = {"reminded_day", "reminded_hour", "rate_asked"}


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, name TEXT, phone TEXT,
                master TEXT, service TEXT, day TEXT, slot TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                reminded_day INTEGER DEFAULT 0,
                reminded_hour INTEGER DEFAULT 0,
                rate_asked INTEGER DEFAULT 0,
                rating INTEGER,
                UNIQUE(master, day, slot)
            );
            CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, phone TEXT);
            CREATE TABLE IF NOT EXISTS blocked_days (day TEXT PRIMARY KEY);
            """
        )


# --- клиенты ---

def get_user(user_id):
    with _conn() as c:
        return c.execute("SELECT name, phone FROM users WHERE user_id = ?", (user_id,)).fetchone()


def save_user(user_id, name, phone):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (user_id, name, phone))


# --- записи ---

def busy_slots(master, day):
    with _conn() as c:
        rows = c.execute("SELECT slot FROM bookings WHERE master = ? AND day = ?", (master, day))
        return {r["slot"] for r in rows}


def add_booking(user_id, name, phone, master, service, day, slot):
    """Возвращает id записи или None, если слот уже заняли (защита от двойной записи)."""
    try:
        with _conn() as c:
            cur = c.execute(
                "INSERT INTO bookings (user_id, name, phone, master, service, day, slot) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, phone, master, service, day, slot),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def user_bookings(user_id):
    with _conn() as c:
        return c.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND day >= date('now', 'localtime') ORDER BY day, slot",
            (user_id,),
        ).fetchall()


def cancel_booking(b_id, user_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM bookings WHERE id = ? AND user_id = ?", (b_id, user_id)).fetchone()
        if row:
            c.execute("DELETE FROM bookings WHERE id = ?", (b_id,))
        return row


def day_bookings(day):
    with _conn() as c:
        return c.execute("SELECT * FROM bookings WHERE day = ? ORDER BY slot, master", (day,)).fetchall()


def bookings_between(start, end):
    with _conn() as c:
        return c.execute(
            "SELECT * FROM bookings WHERE day BETWEEN ? AND ? ORDER BY day, slot", (start, end)
        ).fetchall()


def set_flag(b_id, flag):
    if flag not in FLAGS:
        raise ValueError(flag)
    with _conn() as c:
        c.execute(f"UPDATE bookings SET {flag} = 1 WHERE id = ?", (b_id,))


def set_rating(b_id, user_id, rating):
    with _conn() as c:
        c.execute("UPDATE bookings SET rating = ? WHERE id = ? AND user_id = ?", (rating, b_id, user_id))
        return c.execute("SELECT * FROM bookings WHERE id = ?", (b_id,)).fetchone()


# --- выходные дни ---

def blocked_days():
    with _conn() as c:
        return {r["day"] for r in c.execute("SELECT day FROM blocked_days")}


def toggle_day(day):
    """Закрывает день для записи или открывает обратно. Возвращает True, если день теперь закрыт."""
    with _conn() as c:
        if c.execute("SELECT 1 FROM blocked_days WHERE day = ?", (day,)).fetchone():
            c.execute("DELETE FROM blocked_days WHERE day = ?", (day,))
            return False
        c.execute("INSERT INTO blocked_days VALUES (?)", (day,))
        return True
