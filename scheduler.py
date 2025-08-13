import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.orm import (orm_delete_lists_older_than_sync,
                         orm_get_users_for_warning_sync)
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)

# --- Налаштування планувальника ---
WARNING_HOURS = 36      # Через скільки годин після створення списку надсилати попередження
DELETION_HOURS = 48     # Через скільки годин після створення видаляти список
WARNING_INTERVAL_HOURS = 2 # Як часто перевіряти, чи не час надсилати попередження
CLEANUP_TIME = {"hour": 4, "minute": 0} # О котрій годині ночі запускати повну очистку


async def send_deletion_warnings(bot: Bot):
    """
    Надсилає попередження користувачам, чиї списки будуть скоро видалені.

    Завдання запускається періодично. Воно отримує ID користувачів, які мають
    списки, створені в проміжку між `WARNING_HOURS` та `DELETION_HOURS`,
    та надсилає їм повідомлення.

    Args:
        bot: Екземпляр бота для надсилання повідомлень.
    """
    logger.info("Планувальник: запуск завдання 'send_deletion_warnings'.")
    
    try:
        user_ids = orm_get_users_for_warning_sync(
            hours_warn=WARNING_HOURS,
            hours_expire=DELETION_HOURS
        )
        
        if not user_ids:
            logger.info("Планувальник: користувачів для попередження не знайдено.")
            return

        logger.info("Планувальник: знайдено %d користувачів для попередження.", len(user_ids))
        success_count = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, LEXICON.DELETE_WARNING_MESSAGE)
                success_count += 1
            except Exception as e:
                # Помилка може виникнути, якщо користувач заблокував бота.
                # Це очікувана ситуація, тому логуємо як попередження.
                logger.warning(
                    "Планувальник: не вдалося надіслати попередження користувачу %s: %s",
                    user_id, e
                )

        logger.info("Планувальник: успішно надіслано %d з %d попереджень.", success_count, len(user_ids))
    except Exception as e:
        logger.critical("Планувальник: критична помилка у 'send_deletion_warnings': %s", e, exc_info=True)


async def perform_full_cleanup():
    """
    Виконує повне очищення старих списків, що старші за `DELETION_HOURS`.

    Завдання зазвичай запускається раз на добу вночі.
    """
    logger.warning("Планувальник: запуск завдання 'perform_full_cleanup'.")
    
    try:
        # Синхронна функція orm_delete_lists_older_than_sync видаляє записи
        # з БД та відповідні файли з диска.
        deleted_count = orm_delete_lists_older_than_sync(hours=DELETION_HOURS)
        
        if deleted_count > 0:
            logger.warning("Планувальник: видалено %d старих списків.", deleted_count)
        else:
            logger.info("Планувальник: старі списки для видалення відсутні.")
    except Exception as e:
        logger.critical("Планувальник: критична помилка у 'perform_full_cleanup': %s", e, exc_info=True)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Налаштовує та повертає екземпляр планувальника завдань.

    Args:
        bot: Екземпляр бота, який буде передано до завдань.

    Returns:
        Налаштований екземпляр AsyncIOScheduler.
    """
    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv") # Явно вказуємо часову зону

    try:
        # Додаємо завдання для надсилання попереджень
        scheduler.add_job(
            send_deletion_warnings,
            "interval",
            hours=WARNING_INTERVAL_HOURS,
            args=[bot],
            id="deletion_warnings_job",
            next_run_time=datetime.now() # Запустити одразу при старті
        )

        # Додаємо завдання для нічної очистки
        scheduler.add_job(
            perform_full_cleanup,
            "cron",
            **CLEANUP_TIME,
            id="daily_cleanup_job"
        )
        
        logger.info("Планувальник завдань успішно налаштовано.")
        
    except Exception as e:
        logger.critical("Помилка налаштування планувальника: %s", e, exc_info=True)
        raise

    return scheduler