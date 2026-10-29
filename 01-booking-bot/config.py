"""Настройки бизнеса: всё, что меняется под конкретного клиента, — здесь.

Под нового клиента код не трогаем: копируем business.example.json в business.json
и вписываем его мастеров, услуги и часы работы. Без business.json бот работает как демо.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
# Прокси для доступа к Telegram (VPN-клиенты обычно дают http://127.0.0.1:порт)
PROXY = os.getenv("PROXY") or os.getenv("HTTPS_PROXY") or ""

DEMO = {
    "name": "Барбершоп «Лезвие»",
    "emoji": "💈",
    "address": "ул. Примерная, 1",
    "phone": "+7 (900) 000-00-00",
    "masters": {
        "alex": {"name": "Алексей", "about": "Топ-барбер, 8 лет опыта, фейды и классика"},
        "dima": {"name": "Дмитрий", "about": "Бороды и опасная бритва, 5 лет опыта"},
        "ivan": {"name": "Иван", "about": "Креативные стрижки, 3 года опыта"},
    },
    # ключ: [название, цена в рублях]
    "services": {
        "haircut": ["Мужская стрижка", 1200],
        "beard": ["Оформление бороды", 800],
        "combo": ["Стрижка + борода", 1800],
        "kids": ["Детская стрижка", 900],
    },
    "hours": [10, 20],  # слоты с 10:00 до 19:00
    "days_ahead": 7,
}

_file = Path(__file__).with_name(os.getenv("BUSINESS_FILE", "business.json"))
_biz = {**DEMO, **json.loads(_file.read_text(encoding="utf-8"))} if _file.exists() else DEMO

BUSINESS_NAME = _biz["name"]
ADDRESS = _biz["address"]
PHONE = _biz["phone"]
EMOJI = _biz["emoji"]
MASTERS = _biz["masters"]
SERVICES = {key: tuple(value) for key, value in _biz["services"].items()}
WORK_HOURS = range(*_biz["hours"])
DAYS_AHEAD = _biz["days_ahead"]
