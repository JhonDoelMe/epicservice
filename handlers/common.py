import logging
from typing import NoReturn

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS
from keyboards.reply import admin_main_kb, user_main_kb
from lexicon.lexicon import LEXICON

# Налаштування логування
logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message) -> NoReturn:
    """
    Обробник команди /start. Визначає роль користувача та надає відповідний інтерфейс.
    
    Args:
        message: Об'єкт вхідного повідомлення від користувача
        
    Raises:
        SQLAlchemyError: У разі помилки роботи з базою даних
    """
    user_id = message.from_user.id
    try:
        logger.info("Обробка команди /start для користувача %s", user_id)
        
        if user_id in ADMIN_IDS:
            await message.answer(
                LEXICON.CMD_START_ADMIN,
                reply_markup=admin_main_kb
            )
            logger.debug("Надано адмін-інтерфейс для %s", user_id)
        else:
            await message.answer(
                LEXICON.CMD_START_USER,
                reply_markup=user_main_kb
            )
            logger.debug("Надано звичайний інтерфейс для %s", user_id)
            
    except SQLAlchemyError as e:
        logger.critical("Помилка БД при обробці /start: %s", e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка в /start: %s", e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)