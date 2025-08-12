from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL

# --- Асинхронна частина (для роботи бота) ---
# Замінюємо 'postgresql+asyncpg' на правильний URL для асинхронного двигуна
async_db_url = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql+asyncpg')
async_engine = create_async_engine(async_db_url, echo=False)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)

# --- Синхронна частина (СПЕЦІАЛЬНО ДЛЯ ІМПОРТУ) ---
# Замінюємо 'postgresql+asyncpg' на URL для звичайного, синхронного драйвера psycopg2
sync_db_url = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql+psycopg2')
sync_engine = create_engine(sync_db_url, echo=False)
# Створюємо фабрику для синхронних сесій
sync_session = sessionmaker(bind=sync_engine)