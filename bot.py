import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from database.orm import create_tables
from handlers import common, admin_panel, user_search, user_lists, archive, error_handler

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    # 1. Критична перевірка наявності токена
    if not BOT_TOKEN:
        logging.critical("Критична помилка: BOT_TOKEN не знайдено. Перевірте .env файл або змінні оточення.")
        sys.exit(1)

    # 2. Перевірка підключення до бази даних
    try:
        await create_tables()
        logging.info("Таблиці в базі даних успішно перевірені/створені.")
    except Exception as e:
        logging.critical(f"Не вдалося підключитися до бази даних та створити таблиці: {e}")
        sys.exit(1)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher()

    # Реєструємо обробник помилок на самому верхньому рівні
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