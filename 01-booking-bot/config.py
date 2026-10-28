"""Настройки бизнеса: всё, что меняется под конкретного клиента, — здесь."""
import os

from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
# Прокси для доступа к Telegram (VPN-клиенты обычно дают http://127.0.0.1:порт)
PROXY = os.getenv("PROXY") or os.getenv("HTTPS_PROXY") or ""

BUSINESS_NAME = "Барбершоп «Лезвие»"
ADDRESS = "ул. Примерная, 1"
PHONE = "+7 (900) 000-00-00"

MASTERS = {
    "alex": {"name": "Алексей", "about": "Топ-барбер, 8 лет опыта, фейды и классика"},
    "dima": {"name": "Дмитрий", "about": "Бороды и опасная бритва, 5 лет опыта"},
    "ivan": {"name": "Иван", "about": "Креативные стрижки, 3 года опыта"},
}

# ключ: (название, цена в рублях)
SERVICES = {
    "haircut": ("Мужская стрижка", 1200),
    "beard": ("Оформление бороды", 800),
    "combo": ("Стрижка + борода", 1800),
    "kids": ("Детская стрижка", 900),
}

WORK_HOURS = range(10, 20)  # слоты с 10:00 до 19:00
DAYS_AHEAD = 7
