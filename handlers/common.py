import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import ADMIN_IDS
from keyboards.reply import admin_main_kb, user_main_kb
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обробник команди /start.

    Аналізує ID користувача, щоб визначити, чи є він адміністратором.
    Надсилає відповідне вітальне повідомлення та клавіатуру
    (адмінську або звичайну).
    """
    user_id = message.from_user.id
    try:
        logger.info("Обробка команди /start для користувача %s.", user_id)
        
        # Перевіряємо, чи є ID користувача у списку адміністраторів
        if user_id in ADMIN_IDS:
            await message.answer(
                LEXICON.CMD_START_ADMIN,
                reply_markup=admin_main_kb
            )
            logger.info("Надано адмін-інтерфейс для %s.", user_id)
        else:
            await message.answer(
                LEXICON.CMD_START_USER,
                reply_markup=user_main_kb
            )
            logger.info("Надано звичайний інтерфейс для %s.", user_id)
            
    except Exception as e:
        # Обробка будь-яких інших непередбачених помилок
        logger.error("Неочікувана помилка в cmd_start для %s: %s", user_id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR)