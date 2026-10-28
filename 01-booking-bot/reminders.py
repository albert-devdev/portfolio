"""Фоновые задачи: напоминания за сутки и за 2 часа, запрос оценки после визита."""
import asyncio
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

import db
import keyboards as kb
from config import ADDRESS

CHECK_EVERY = 60  # секунд


def due_actions(rows, now):
    """Решает, что отправить по каждой записи. Вынесено отдельно, чтобы легко тестировать."""
    actions = []
    for r in rows:
        left = datetime.fromisoformat(f"{r['day']}T{r['slot']}") - now
        if not r["reminded_day"] and timedelta(hours=3) < left <= timedelta(hours=24):
            actions.append((r, "reminded_day"))
        elif not r["reminded_hour"] and timedelta(0) < left <= timedelta(hours=2):
            actions.append((r, "reminded_hour"))
        elif not r["rate_asked"] and -timedelta(hours=24) < left <= -timedelta(hours=1):
            actions.append((r, "rate_asked"))
    return actions


async def check(bot: Bot):
    today = date.today()
    rows = db.bookings_between((today - timedelta(days=1)).isoformat(), (today + timedelta(days=1)).isoformat())
    for r, flag in due_actions(rows, datetime.now()):
        try:
            if flag == "reminded_day":
                await bot.send_message(r["user_id"], "⏰ Напоминаем: завтра у вас запись\n\n" + kb.summary(dict(r)))
            elif flag == "reminded_hour":
                await bot.send_message(r["user_id"], f"⏰ Ждём вас через 2 часа!\n📍 {ADDRESS}\n\n" + kb.summary(dict(r)))
            else:
                await bot.send_message(r["user_id"], "Как вам визит? Оцените, пожалуйста:", reply_markup=kb.rating_kb(r["id"]))
        except TelegramAPIError as e:  # клиент заблокировал бота и т.п. — не повторяем
            logging.warning("Не удалось отправить клиенту %s: %s", r["user_id"], e)
        db.set_flag(r["id"], flag)


async def loop(bot: Bot):
    while True:
        try:
            await check(bot)
        except Exception:
            logging.exception("Ошибка в напоминаниях")
        await asyncio.sleep(CHECK_EVERY)
