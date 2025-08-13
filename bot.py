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
from scheduler import setup_scheduler # <-- ИМПОРТИРУЕМ НАСТРОЙКУ


async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    if not BOT_TOKEN:
        logging.critical("Критична помилка: BOT_TOKEN не знайдено...")
        sys.exit(1)

    try:
        async with async_session() as session:
            await session.execute(text('SELECT 1'))
        logging.info("З'єднання з базою даних успішно встановлено.")
    except Exception as e:
        logging.critical(f"Не вдалося підключитися до бази даних: {e}")
        sys.exit(1)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher()

    # --- ЗАПУСК ПЛАНИРОВЩИКА ---
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logging.info("Планувальник завдань запущено.")
    # ---------------------------

    dp.include_router(error_handler.router)
    dp.include_router(admin_panel.router)
    dp.include_router(common.router)
    dp.include_router(archive.router)
    dp.include_router(user_lists.router)
    dp.include_router(user_search.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено.")