"""Telegram-бот для записи клиентов (салон, барбершоп, автосервис и т.п.).

Клиент выбирает услугу -> дату -> свободное время -> оставляет имя и телефон.
Администратор получает уведомление и может смотреть записи на сегодня.
"""
import asyncio
import logging
import os
import re
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

import db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

SERVICES = {
    "haircut": ("Мужская стрижка", 1200),
    "beard": ("Оформление бороды", 800),
    "combo": ("Стрижка + борода", 1800),
}
WORK_HOURS = range(10, 20)  # слоты с 10:00 до 19:00
DAYS_AHEAD = 7

router = Router()


class Booking(StatesGroup):
    name = State()
    phone = State()


def services_kb():
    kb = InlineKeyboardBuilder()
    for key, (title, price) in SERVICES.items():
        kb.button(text=f"{title} — {price} ₽", callback_data=f"svc:{key}")
    kb.adjust(1)
    return kb.as_markup()


def dates_kb():
    kb = InlineKeyboardBuilder()
    today = date.today()
    for i in range(DAYS_AHEAD):
        d = today + timedelta(days=i)
        kb.button(text=d.strftime("%d.%m (%a)"), callback_data=f"day:{d.isoformat()}")
    kb.adjust(2)
    return kb.as_markup()


def times_kb(day: str):
    kb = InlineKeyboardBuilder()
    busy = db.busy_slots(day)
    now = datetime.now()
    for h in WORK_HOURS:
        slot = f"{h:02d}:00"
        if slot in busy:
            continue
        if day == date.today().isoformat() and h <= now.hour:
            continue
        kb.button(text=slot, callback_data=f"time:{slot}")
    kb.button(text="← Другая дата", callback_data="back:dates")
    kb.adjust(4)
    return kb.as_markup()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здравствуйте! Я помогу записаться к мастеру.\n\nВыберите услугу:",
        reply_markup=services_kb(),
    )


@router.message(Command("my"))
async def my_bookings(message: Message):
    rows = db.user_bookings(message.from_user.id)
    if not rows:
        await message.answer("У вас нет активных записей. Записаться: /start")
        return
    kb = InlineKeyboardBuilder()
    lines = []
    for b_id, day, slot, service in rows:
        lines.append(f"• {day} в {slot} — {SERVICES[service][0]}")
        kb.button(text=f"Отменить {day} {slot}", callback_data=f"cancel:{b_id}")
    kb.adjust(1)
    await message.answer("Ваши записи:\n" + "\n".join(lines), reply_markup=kb.as_markup())


@router.message(Command("today"))
async def today_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    rows = db.day_bookings(date.today().isoformat())
    if not rows:
        await message.answer("На сегодня записей нет.")
        return
    text = "\n".join(f"{slot} — {name}, {phone} ({SERVICES[svc][0]})" for slot, name, phone, svc in rows)
    await message.answer("Записи на сегодня:\n" + text)


@router.callback_query(F.data.startswith("svc:"))
async def pick_service(cb: CallbackQuery, state: FSMContext):
    await state.update_data(service=cb.data.split(":", 1)[1])
    await cb.message.edit_text("Выберите дату:", reply_markup=dates_kb())
    await cb.answer()


@router.callback_query(F.data == "back:dates")
async def back_to_dates(cb: CallbackQuery):
    await cb.message.edit_text("Выберите дату:", reply_markup=dates_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("day:"))
async def pick_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.split(":", 1)[1]
    await state.update_data(day=day)
    await cb.message.edit_text(f"Свободное время на {day}:", reply_markup=times_kb(day))
    await cb.answer()


@router.callback_query(F.data.startswith("time:"))
async def pick_time(cb: CallbackQuery, state: FSMContext):
    await state.update_data(slot=cb.data.split(":", 1)[1])
    await state.set_state(Booking.name)
    await cb.message.edit_text("Как к вам обращаться? Напишите имя.")
    await cb.answer()


@router.message(Booking.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip()[:50])
    await state.set_state(Booking.phone)
    await message.answer("Укажите номер телефона (например, +79991234567):")


@router.message(Booking.phone)
async def get_phone(message: Message, state: FSMContext, bot: Bot):
    phone = re.sub(r"[^\d+]", "", message.text or "")
    if not re.fullmatch(r"\+?\d{10,15}", phone):
        await message.answer("Похоже, номер с ошибкой. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    ok = db.add_booking(message.from_user.id, data["name"], phone, data["service"], data["day"], data["slot"])
    await state.clear()
    if not ok:
        await message.answer("Увы, это время только что заняли. Выберите другое: /start")
        return
    title, price = SERVICES[data["service"]]
    await message.answer(
        f"Готово! Вы записаны:\n{title} — {price} ₽\n{data['day']} в {data['slot']}\n\n"
        "Посмотреть или отменить запись: /my"
    )
    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"🆕 Новая запись\n{data['day']} {data['slot']}\n{title}\n{data['name']}, {phone}",
        )


@router.callback_query(F.data.startswith("cancel:"))
async def cancel(cb: CallbackQuery, bot: Bot):
    b_id = int(cb.data.split(":", 1)[1])
    info = db.cancel_booking(b_id, cb.from_user.id)
    if info:
        await cb.message.edit_text("Запись отменена. Записаться снова: /start")
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"❌ Отмена записи: {info[0]} {info[1]}")
    await cb.answer()


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в файле .env (см. .env.example)")
    logging.basicConfig(level=logging.INFO)
    db.init()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
