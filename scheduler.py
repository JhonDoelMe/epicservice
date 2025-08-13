# scheduler.py
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.orm import (orm_delete_lists_older_than_sync,
                          orm_get_users_for_warning_sync)
from lexicon.lexicon import LEXICON


async def send_deletion_warnings(bot: Bot):
    """Отправляет предупреждения пользователям, чьи списки скоро будут удалены."""
    logging.info("Scheduler: Running job 'send_deletion_warnings'.")
    
    # Получаем ID пользователей, которых нужно предупредить
    user_ids = orm_get_users_for_warning_sync(
        hours_warn=36, hours_expire=48
    )
    
    if not user_ids:
        logging.info("Scheduler: No users found for deletion warning.")
        return

    logging.info(f"Scheduler: Found {len(user_ids)} users to warn.")
    count = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, LEXICON.DELETE_WARNING_MESSAGE)
            count += 1
        except Exception as e:
            # Логируем ошибку, если не смогли отправить сообщение (например, бот заблокирован)
            logging.error(f"Scheduler: Failed to send warning to user {user_id}. Error: {e}")
    logging.info(f"Scheduler: Successfully sent warnings to {count} users.")


async def perform_full_cleanup():
    """Полностью удаляет старые списки (старше 48 часов)."""
    logging.warning("!!!SCHEDULER ACTION!!! Running job 'perform_full_cleanup'.")
    
    # Вызываем функцию удаления и получаем количество удаленных списков
    deleted_count = orm_delete_lists_older_than_sync(hours=48)
    
    if deleted_count > 0:
        logging.warning(f"Scheduler: Successfully deleted {deleted_count} lists older than 48 hours.")
    else:
        logging.info("Scheduler: No old lists to delete.")


def setup_scheduler(bot: Bot):
    """Настраивает и запускает все запланированные задачи."""
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")

    # Задача №1: Отправка предупреждений.
    # Запускается каждые 2 часа.
    scheduler.add_job(
        send_deletion_warnings,
        "interval",
        hours=2,
        args=[bot],
        next_run_time=datetime.now() # Запустить сразу при старте
    )

    # Задача №2: Полная очистка.
    # Запускается один раз в сутки, в 4 часа утра.
    scheduler.add_job(
        perform_full_cleanup,
        "cron",
        hour=4,
        minute=0
    )
    
    return scheduler