import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job

from database.orm import (orm_delete_lists_older_than_sync,
                         orm_get_users_for_warning_sync)
from lexicon.lexicon import LEXICON

# Налаштування логування
logger = logging.getLogger(__name__)

# Конфігурація планувальника
WARNING_HOURS = 36
DELETION_HOURS = 48
WARNING_INTERVAL_HOURS = 2
CLEANUP_TIME = {"hour": 4, "minute": 0}

async def send_deletion_warnings(bot: Bot) -> None:
    """
    Надсилає попередження користувачам, чиї списки будуть скоро видалені.
    
    Args:
        bot: Екземпляр бота для відправки повідомлень
    """
    logger.info("Запуск завдання: відправка попереджень про видалення")
    
    try:
        user_ids = orm_get_users_for_warning_sync(
            hours_warn=WARNING_HOURS,
            hours_expire=DELETION_HOURS
        )
        
        if not user_ids:
            logger.info("Користувачів для попередження не знайдено")
            return

        logger.info("Знайдено %s користувачів для попередження", len(user_ids))
        success_count = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, LEXICON.DELETE_WARNING_MESSAGE)
                success_count += 1
            except Exception as e:
                logger.warning(
                    "Не вдалося надіслати попередження користувачу %s: %s",
                    user_id, e
                )

        logger.info("Успішно надіслано %s попереджень", success_count)
    except Exception as e:
        logger.critical("Критична помилка при відправці попереджень: %s", e)

async def perform_full_cleanup() -> None:
    """Виконує повне очищення старих списків."""
    logger.warning("Запуск завдання: очищення старих списків")
    
    try:
        deleted_count = orm_delete_lists_older_than_sync(hours=DELETION_HOURS)
        
        if deleted_count > 0:
            logger.warning("Видалено %s старих списків", deleted_count)
        else:
            logger.info("Старі списки для видалення відсутні")
    except Exception as e:
        logger.critical("Критична помилка при очищенні списків: %s", e)

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Налаштовує та запускає планувальник завдань.
    
    Args:
        bot: Екземпляр бота для передачі в завдання
        
    Returns:
        Налаштований екземпляр планувальника
    """
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

    try:
        # Завдання попереджень
        scheduler.add_job(
            send_deletion_warnings,
            "interval",
            hours=WARNING_INTERVAL_HOURS,
            args=[bot],
            next_run_time=datetime.now(),
            id="deletion_warnings"
        )

        # Завдання очищення
        scheduler.add_job(
            perform_full_cleanup,
            "cron",
            **CLEANUP_TIME,
            id="daily_cleanup"
        )
        
        logger.info("Планувальник успішно налаштовано")
    except Exception as e:
        logger.critical("Помилка налаштування планувальника: %s", e)
        raise

    return scheduler