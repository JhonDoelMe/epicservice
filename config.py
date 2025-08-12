import os
from dotenv import load_dotenv
import logging

load_dotenv()

# --- BOT ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Безпечний парсинг ADMIN_IDS
try:
    # Фільтруємо порожні строки, які можуть з'явитися, якщо в кінці коми
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id]
except (ValueError, TypeError):
    logging.warning("ADMIN_IDS не вдалося завантажити. Перевірте формат у .env файлі. Очікується 'ID1,ID2,ID3'")
    ADMIN_IDS = []


# --- DATABASE ---
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SYNC_DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- STORAGE ---
# Новий розділ для шляхів
ARCHIVES_PATH = "archives"