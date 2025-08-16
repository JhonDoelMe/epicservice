# epicservice/utils/force_save_helper.py

import logging
import os

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.exc import SQLAlchemyError

from database.engine import async_session
from lexicon.lexicon import LEXICON
# --- ЗМІНА: Імпортуємо наш новий централізований сервіс ---
from utils.list_processor import process_and_save_list

logger = logging.getLogger(__name__)


async def force_save_user_list(user_id: int, bot: Bot) -> bool:
    """
    Примусово зберігає тимчасовий список вказаного користувача.

    Використовує централізовану функцію process_and_save_list,
    а потім надсилає згенеровані файли користувачу.

    Args:
        user_id: ID користувача, чий список потрібно зберегти.
        bot: Екземпляр бота для надсилання повідомлень/файлів.

    Returns:
        True, якщо збереження пройшло успішно, інакше False.
    """
    main_list_path = None
    surplus_list_path = None
    
    try:
        async with async_session() as session:
            async with session.begin():
                # --- ЗМІНА: Вся логіка тепер в одній функції ---
                main_list_path, surplus_list_path = await process_and_save_list(session, user_id)

        # --- Надсилання файлів користувачу після успішної транзакції ---
        if not main_list_path and not surplus_list_path:
            # Якщо список був порожній, нічого не надсилаємо, операція успішна
            return True
            
        if main_list_path:
            await bot.send_document(user_id, FSInputFile(main_list_path), caption=LEXICON.MAIN_LIST_SAVED)
        if surplus_list_path:
            await bot.send_document(user_id, FSInputFile(surplus_list_path), caption=LEXICON.SURPLUS_LIST_CAPTION)
        
        return True

    except (SQLAlchemyError, ValueError) as e:
        logger.error("Помилка транзакції при примусовому збереженні для %s: %s", user_id, e, exc_info=True)
        try:
            await bot.send_message(user_id, LEXICON.TRANSACTION_ERROR)
        except Exception as bot_error:
            logger.warning("Не вдалося надіслати повідомлення про помилку користувачу %s: %s", user_id, bot_error)
        return False
    except Exception as e:
        logger.error("Неочікувана помилка при примусовому збереженні для %s: %s", user_id, e, exc_info=True)
        try:
            await bot.send_message(user_id, LEXICON.UNEXPECTED_ERROR)
        except Exception as bot_error:
            logger.warning("Не вдалося надіслати повідомлення про помилку користувачу %s: %s", user_id, bot_error)
        return False
    finally:
        # Прибираємо тимчасові файли
        if main_list_path and os.path.exists(main_list_path):
            os.remove(main_list_path)
        if surplus_list_path and os.path.exists(surplus_list_path):
            os.remove(surplus_list_path)