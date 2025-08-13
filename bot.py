import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import text

from config import BOT_TOKEN
from database.engine import async_session
from handlers import (admin_panel, archive, common, error_handler, user_lists,
                      user_search)
from scheduler import setup_scheduler


async def main():
    # Налаштування логування
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log')
        ]
    )
    logger = logging.getLogger(__name__)
    
    if not BOT_TOKEN:
        logger.critical("Критична помилка: BOT_TOKEN не знайдено у конфігурації")
        sys.exit(1)

    # Перевірка підключення до БД
    try:
        async with async_session() as session:
            await session.execute(text('SELECT 1'))
        logger.info("Підключення до бази даних успішне")
    except Exception as e:
        logger.critical("Помилка підключення до бази даних: %s", exc_info=True)
        sys.exit(1)
    
    # Ініціалізація бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(
        parse_mode="Markdown",
        link_preview_is_disabled=True
    ))
    dp = Dispatcher()

    # Запуск планувальника завдань
    scheduler = setup_scheduler(bot)
    try:
        scheduler.start()
        logger.info("Сервіс планувальника завдань успішно запущено")
        
        # Підключення роутерів
        routers = [
            error_handler.router,
            admin_panel.router,
            common.router,
            archive.router,
            user_lists.router,
            user_search.router
        ]
        
        for router in routers:
            dp.include_router(router)
            logger.debug("Підключено роутер: %s", router.__class__.__name__)

        # Запуск бота
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот запускається...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical("Критична помилка під час роботи бота: %s", e, exc_info=True)
        raise
    finally:
        logger.info("Завершення роботи бота...")
        if 'scheduler' in locals():
            scheduler.shutdown()
            logger.info("Планувальник завдань зупинено")
        await bot.session.close()
        logger.info("Сесія бота закрита")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено користувачем")
    except Exception as e:
        logging.critical("Неочікувана помилка: %s", e, exc_info=True)
        sys.exit(1)