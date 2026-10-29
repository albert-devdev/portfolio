"""Клавиатуры и форматирование: всё, что видит пользователь."""
from datetime import date, datetime, timedelta

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from config import DAYS_AHEAD, EMOJI, MASTERS, SERVICES, WORK_HOURS

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def plural(n: int, one: str, few: str, many: str) -> str:
    """plural(5, 'запись', 'записи', 'записей') -> '5 записей'"""
    if n % 10 == 1 and n % 100 != 11:
        word = one
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = few
    else:
        word = many
    return f"{n} {word}"


def fmt_day(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d:%d.%m} ({WEEKDAYS[d.weekday()]})"


def summary(data: dict) -> str:
    title, price = SERVICES[data["service"]]
    lines = [
        f"{EMOJI} Мастер: {MASTERS[data['master']]['name']}",
        f"🧾 {title} — {price} ₽",
        f"📅 {fmt_day(data['day'])} в {data['slot']}",
    ]
    if data.get("name"):
        lines.append(f"👤 {data['name']}, {data['phone']}")
    return "\n".join(lines)


def free_slots(master: str, day: str) -> list[str]:
    busy = db.busy_slots(master, day)
    now = datetime.now()
    is_today = day == date.today().isoformat()
    return [
        f"{h:02d}:00" for h in WORK_HOURS
        if f"{h:02d}:00" not in busy and not (is_today and h <= now.hour)
    ]


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Записаться", callback_data="menu:book")
    kb.button(text="🗂 Мои записи", callback_data="menu:my")
    kb.button(text=f"{EMOJI} О нас", callback_data="menu:about")
    kb.adjust(1, 2)
    return kb.as_markup()


def back_home():
    kb = InlineKeyboardBuilder()
    kb.button(text="← В меню", callback_data="menu:home")
    return kb.as_markup()


def masters_kb():
    kb = InlineKeyboardBuilder()
    for key, m in MASTERS.items():
        kb.button(text=f"{m['name']} · {m['about']}", callback_data=f"master:{key}")
    kb.button(text="← В меню", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def services_kb():
    kb = InlineKeyboardBuilder()
    for key, (title, price) in SERVICES.items():
        kb.button(text=f"{title} — {price} ₽", callback_data=f"svc:{key}")
    kb.button(text="← Другой мастер", callback_data="menu:book")
    kb.adjust(1)
    return kb.as_markup()


def dates_kb(master: str):
    kb = InlineKeyboardBuilder()
    blocked = db.blocked_days()
    today = date.today()
    for i in range(DAYS_AHEAD):
        day = (today + timedelta(days=i)).isoformat()
        if day in blocked:
            continue
        left = len(free_slots(master, day))
        if left:
            kb.button(text=f"{fmt_day(day)} · {plural(left, 'окно', 'окна', 'окон')}", callback_data=f"day:{day}")
    kb.button(text="← Другая услуга", callback_data="back:services")
    kb.adjust(2)
    return kb.as_markup()


def times_kb(master: str, day: str):
    kb = InlineKeyboardBuilder()
    for slot in free_slots(master, day):
        kb.button(text=slot, callback_data=f"time:{slot}")
    kb.button(text="← Другая дата", callback_data="back:dates")
    kb.adjust(4)
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm:yes")
    kb.button(text="✏️ Изменить имя/телефон", callback_data="confirm:edit")
    kb.button(text="✖ Отмена", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def my_bookings_kb(rows):
    kb = InlineKeyboardBuilder()
    for r in rows:
        kb.button(text=f"✖ Отменить {fmt_day(r['day'])} {r['slot']}", callback_data=f"cancel:{r['id']}")
    kb.button(text="← В меню", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def rating_kb(b_id: int):
    kb = InlineKeyboardBuilder()
    for n in range(1, 6):
        kb.button(text="⭐" * n, callback_data=f"rate:{b_id}:{n}")
    kb.adjust(1)
    return kb.as_markup()
