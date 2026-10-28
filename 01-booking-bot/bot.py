"""Telegram-бот для записи клиентов (барбершоп, салон, автосервис и т.п.).

Клиент: мастер -> услуга -> дата -> свободное время -> подтверждение.
Постоянных клиентов бот узнаёт и не спрашивает имя и телефон повторно.
Бот сам напоминает о визите и после него просит оценку.
Администратор: /admin — расписание, статистика, выгрузка в Excel, выходные дни.
"""
import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import admin
import db
import keyboards as kb
import reminders
from config import ADDRESS, ADMIN_ID, BOT_TOKEN, BUSINESS_NAME, MASTERS, PHONE, PROXY, SERVICES

router = Router()


class Booking(StatesGroup):
    name = State()
    phone = State()


async def notify_admin(bot: Bot, text: str):
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, text)


# --- главное меню ---

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    user = db.get_user(message.from_user.id)
    hello = f"С возвращением, {user['name']}! 👋" if user else "Здравствуйте! 👋"
    await message.answer(
        f"{hello}\nЭто бот записи в {BUSINESS_NAME}.\nЗапись занимает 30 секунд — без звонков.",
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "menu:home")
async def home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Главное меню:", reply_markup=kb.main_menu())
    await cb.answer()


@router.callback_query(F.data == "menu:about")
async def about(cb: CallbackQuery):
    masters = "\n".join(f"• {m['name']} — {m['about']}" for m in MASTERS.values())
    prices = "\n".join(f"• {title} — {price} ₽" for title, price in SERVICES.values())
    await cb.message.edit_text(
        f"💈 {BUSINESS_NAME}\n📍 {ADDRESS}\n📞 {PHONE}\n\nМастера:\n{masters}\n\nЦены:\n{prices}",
        reply_markup=kb.back_home(),
    )
    await cb.answer()


# --- запись: мастер -> услуга -> дата -> время ---

@router.callback_query(F.data == "menu:book")
async def choose_master(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Выберите мастера:", reply_markup=kb.masters_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("master:"))
async def pick_master(cb: CallbackQuery, state: FSMContext):
    await state.update_data(master=cb.data.split(":", 1)[1])
    await cb.message.edit_text("Выберите услугу:", reply_markup=kb.services_kb())
    await cb.answer()


@router.callback_query(F.data == "back:services")
async def back_services(cb: CallbackQuery):
    await cb.message.edit_text("Выберите услугу:", reply_markup=kb.services_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("svc:"))
async def pick_service(cb: CallbackQuery, state: FSMContext):
    await state.update_data(service=cb.data.split(":", 1)[1])
    await show_dates(cb, state)


@router.callback_query(F.data == "back:dates")
async def show_dates(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "master" not in data:  # состояние потерялось, например после перезапуска бота
        await cb.message.edit_text("Начнём заново:", reply_markup=kb.main_menu())
        return await cb.answer()
    name = MASTERS[data["master"]]["name"]
    await cb.message.edit_text(f"Ближайшие свободные дни у мастера {name}:", reply_markup=kb.dates_kb(data["master"]))
    await cb.answer()


@router.callback_query(F.data.startswith("day:"))
async def pick_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.split(":", 1)[1]
    data = await state.update_data(day=day)
    await cb.message.edit_text(f"Свободное время на {kb.fmt_day(day)}:", reply_markup=kb.times_kb(data["master"], day))
    await cb.answer()


@router.callback_query(F.data.startswith("time:"))
async def pick_time(cb: CallbackQuery, state: FSMContext):
    data = await state.update_data(slot=cb.data.split(":", 1)[1])
    user = db.get_user(cb.from_user.id)
    if user:
        data = await state.update_data(name=user["name"], phone=user["phone"])
        await cb.message.edit_text("Проверьте запись:\n\n" + kb.summary(data), reply_markup=kb.confirm_kb())
    else:
        await state.set_state(Booking.name)
        await cb.message.edit_text(kb.summary(data) + "\n\nКак к вам обращаться? Напишите имя.")
    await cb.answer()


# --- контакты (только для новых клиентов) ---

@router.callback_query(F.data == "confirm:edit")
async def edit_contacts(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Booking.name)
    await cb.message.edit_text("Как к вам обращаться? Напишите имя.")
    await cb.answer()


@router.message(Booking.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=(message.text or "").strip()[:50] or "Клиент")
    await state.set_state(Booking.phone)
    await message.answer("Нажмите кнопку ниже или напишите номер вручную:", reply_markup=kb.phone_kb())


@router.message(Booking.phone)
async def get_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else (message.text or "")
    phone = re.sub(r"[^\d+]", "", raw)
    if not re.fullmatch(r"\+?\d{10,15}", phone):
        await message.answer("Похоже, номер с ошибкой. Попробуйте ещё раз:")
        return
    data = await state.update_data(phone=phone)
    db.save_user(message.from_user.id, data["name"], phone)
    await state.set_state(None)
    await message.answer("Спасибо! Номер сохранён.", reply_markup=ReplyKeyboardRemove())
    await message.answer("Проверьте запись:\n\n" + kb.summary(data), reply_markup=kb.confirm_kb())


@router.callback_query(F.data == "confirm:yes")
async def confirm(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not {"master", "service", "day", "slot", "name"} <= data.keys():
        await cb.message.edit_text("Сессия устарела, начнём заново:", reply_markup=kb.main_menu())
        return await cb.answer()
    b_id = db.add_booking(cb.from_user.id, data["name"], data["phone"], data["master"],
                          data["service"], data["day"], data["slot"])
    await state.clear()
    if not b_id:
        await cb.message.edit_text("Увы, это время только что заняли 😔", reply_markup=kb.main_menu())
        return await cb.answer()
    await cb.message.edit_text(
        "🎉 Вы записаны!\n\n" + kb.summary(data) +
        f"\n\n📍 {ADDRESS}\nНапомним за день и за 2 часа до визита.",
        reply_markup=kb.main_menu(),
    )
    await notify_admin(bot, "🆕 Новая запись\n\n" + kb.summary(data))
    await cb.answer("Готово!")


# --- мои записи ---

@router.message(Command("my"))
@router.callback_query(F.data == "menu:my")
async def my_bookings(event: Message | CallbackQuery):
    rows = db.user_bookings(event.from_user.id)
    if rows:
        text = "Ваши записи:\n\n" + "\n\n".join(kb.summary(dict(r)) for r in rows)
        markup = kb.my_bookings_kb(rows)
    else:
        text, markup = "У вас нет предстоящих записей.", kb.main_menu()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("cancel:"))
async def cancel(cb: CallbackQuery, bot: Bot):
    row = db.cancel_booking(int(cb.data.split(":", 1)[1]), cb.from_user.id)
    if row:
        await cb.message.edit_text("Запись отменена. Будем ждать вас в другой раз!", reply_markup=kb.main_menu())
        await notify_admin(bot, "❌ Отмена записи\n\n" + kb.summary(dict(row)))
    await cb.answer()


# --- оценка после визита ---

@router.callback_query(F.data.startswith("rate:"))
async def rate(cb: CallbackQuery, bot: Bot):
    _, b_id, n = cb.data.split(":")
    row = db.set_rating(int(b_id), cb.from_user.id, int(n))
    await cb.message.edit_text("Спасибо за оценку! ❤️ Будем рады видеть вас снова.", reply_markup=kb.main_menu())
    if row:
        await notify_admin(bot, f"{'⭐' * int(n)} Оценка от {row['name']} (мастер {MASTERS[row['master']]['name']})")
    await cb.answer()


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в файле .env (см. .env.example)")
    logging.basicConfig(level=logging.INFO)
    db.init()
    bot = Bot(BOT_TOKEN, session=AiohttpSession(proxy=PROXY) if PROXY else None)
    dp = Dispatcher()
    dp.include_routers(admin.router, router)
    asyncio.create_task(reminders.loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
