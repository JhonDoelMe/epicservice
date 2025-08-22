import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

# --- ЗМІНА: Видаляємо SYNC_DATABASE_URL ---
from config import DATABASE_URL
from database.models import Base

# Налаштування логера для цього модуля
logger = logging.getLogger(__name__)

# --- НОВА ФУНКЦІЯ: Для ініціалізації таблиць ---
async def create_tables():
    """
    Асинхронно створює таблиці в базі даних на основі моделей SQLAlchemy.
    """
    logger.info("Починаю створення таблиць в БД...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Створення таблиць завершено.")

try:
    # --- Асинхронна частина (для роботи бота) ---
    async_engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    
    async_session = async_sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        autoflush=False
    )
    
    # --- ВИДАЛЕНО: Синхронна частина, яка була потрібна для Alembic ---
    
    logger.info("Асинхронне підключення до бази даних успішно ініціалізовано.")
    
except Exception as e:
    logger.critical("Критична помилка ініціалізації підключення до БД: %s", e, exc_info=True)
    raise