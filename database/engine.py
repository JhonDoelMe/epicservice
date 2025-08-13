from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging

from config import DATABASE_URL

# Налаштування логування
logger = logging.getLogger(__name__)

try:
    # --- Асинхронна частина (для роботи бота) ---
    async_engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Перевіряє з'єднання перед використанням
        pool_recycle=3600    # Оновлює з'єднання кожну годину
    )
    async_session = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
        autoflush=False
    )
    
    # --- Синхронна частина (для імпорту даних) ---
    sync_db_url = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql+psycopg2')
    sync_engine = create_engine(
        sync_db_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    sync_session = sessionmaker(
        bind=sync_engine,
        autocommit=False,
        autoflush=False
    )
    
    logger.info("Підключення до бази даних успішно ініціалізовано")
    
except Exception as e:
    logger.critical("Помилка ініціалізації підключення до БД: %s", e)
    raise