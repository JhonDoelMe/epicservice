import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from sqlalchemy import text

from config import BOT_TOKEN, ADMIN_IDS
from database.engine import async_session
from handlers import (admin_panel, archive, common, error_handler, user_lists,
                      user_search)
from keyboards.reply import user_main_kb, admin_main_kb
from scheduler import setup_scheduler


async def set_main_menu(bot: Bot):
    """
    Встановлює головне меню (команди) для користувачів та адміністраторів.
    """
    main_menu_commands = [
        BotCommand(command='/start', description='Перезапустити бота')
    ]
    await bot.set_my_commands(main_menu_commands)


async def main():
    """
    Головна асинхронна функція для ініціалізації та запуску бота.
    """
    # 1. Налаштування логування
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout), # Вивід логів у консоль
            logging.FileHandler('bot.log', mode='a') # Запис логів у файл
        ]
    )
    logger = logging.getLogger(__name__)
    
    # Перевірка наявності токена
    if not BOT_TOKEN:
        logger.critical("Критична помилка: BOT_TOKEN не знайдено! Перевірте ваш .env файл.")
        sys.exit(1)

    # 2. Перевірка підключення до бази даних
    try:
        async with async_session() as session:
            await session.execute(text('SELECT 1'))
        logger.info("Підключення до бази даних успішне.")
    except Exception as e:
        logger.critical("Помилка підключення до бази даних: %s", e, exc_info=True)
        sys.exit(1)
    
    # 3. Ініціалізація бота та диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(
        parse_mode="Markdown",
        link_preview_is_disabled=True
    ))
    dp = Dispatcher()

    # 4. Налаштування та запуск планувальника
    # Планувальник відповідає за фонові задачі (напр., видалення старих списків)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Сервіс планувальника завдань успішно запущено.")

    # 5. Реєстрація роутерів (обробників повідомлень)
    # Порядок реєстрації важливий!
    dp.include_router(error_handler.router) # Обробник помилок має бути першим
    dp.include_router(admin_panel.router)   # Спочатку специфічні роутери (адмін)
    dp.include_router(common.router)        # Загальні команди (/start)
    dp.include_router(archive.router)       # Обробники кнопок меню
    dp.include_router(user_lists.router)    # Обробники кнопок меню та станів FSM
    dp.include_router(user_search.router)   # Обробник пошуку (ловить будь-який текст) має бути останнім

    try:
        # Встановлюємо меню команд
        await set_main_menu(bot)
        
        # Видаляємо вебхук та накопичені оновлення
        await bot.delete_webhook(drop_pending_updates=True)
        
        logger.info("Бот запускається...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical("Критична помилка під час роботи бота: %s", e, exc_info=True)
    finally:
        logger.info("Завершення роботи бота...")
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Планувальник завдань зупинено.")
        await bot.session.close()
        logger.info("Сесія бота закрита.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено користувачем.")
    except Exception as e:
        logging.critical("Неочікувана помилка на верхньому рівні: %s", e, exc_info=True)
        sys.exit(1)