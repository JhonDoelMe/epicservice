import logging
import os
from typing import List

from dotenv import load_dotenv

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Завантаження .env файла
if not load_dotenv():
    logger.warning("Не вдалося завантажити .env файл або він відсутній")

def get_required_env(var_name: str) -> str:
    """Отримання обов'язкової змінної оточення"""
    value = os.getenv(var_name)
    if not value:
        logger.critical(f"Відсутня обов'язкова змінна оточення: {var_name}")
        raise ValueError(f"Відсутня обов'язкова змінна оточення: {var_name}")
    return value

# --- BOT ---
BOT_TOKEN = get_required_env("BOT_TOKEN")

# Безпечний парсинг ADMIN_IDS
def get_admin_ids() -> List[int]:
    """Отримання списку ID адміністраторів"""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    try:
        return [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id]
    except (ValueError, TypeError) as e:
        logger.warning(
            "ADMIN_IDS не вдалося завантажити. Перевірте формат у .env файлі. "
            "Очікується 'ID1,ID2,ID3'. Помилка: %s", e
        )
        return []

ADMIN_IDS = get_admin_ids()

# --- DATABASE ---
def validate_db_port(port: str) -> int:
    """Валідація порту бази даних"""
    try:
        port_int = int(port)
        if not 0 < port_int < 65536:
            raise ValueError("Порт повинен бути в діапазоні 1-65535")
        return port_int
    except ValueError as e:
        logger.critical("Невірний формат порту БД: %s", e)
        raise

DB_USER = get_required_env("DB_USER")
DB_PASS = get_required_env("DB_PASS")
DB_HOST = get_required_env("DB_HOST")
DB_PORT = validate_db_port(get_required_env("DB_PORT"))
DB_NAME = get_required_env("DB_NAME")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SYNC_DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- STORAGE ---
ARCHIVES_PATH = "archives"