import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from database.orm import create_tables
from handlers import common, admin_panel, user_search, user_lists, archive # <-- Додано archive

async def main():
    logging.basicConfig(level=logging.INFO)
    await create_tables()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher()

    dp.include_router(admin_panel.router)
    dp.include_router(common.router)
    dp.include_router(archive.router) # <-- Зареєстровано новий роутер
    dp.include_router(user_lists.router)
    dp.include_router(user_search.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено.")