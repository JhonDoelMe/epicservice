# epicservice/handlers/common.py

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import ADMIN_IDS
# Імпортуємо нову функцію для роботи з користувачами
from database.orm import orm_upsert_user
# --- ЗМІНА: Імпортуємо нові inline-клавіатури ---
from keyboards.inline import get_admin_main_kb, get_user_main_kb
# --- ВИДАЛЕНО: Старі reply-клавіатури ---
# from keyboards.reply import admin_main_kb, user_main_kb
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обробник команди /start.

    Зберігає або оновлює інформацію про користувача в базі даних,
    а потім надсилає відповідне вітальне повідомлення та клавіатуру.
    """
    user = message.from_user
    try:
        # ВИПРАВЛЕНО: Додано збереження користувача в БД при кожному /start
        await orm_upsert_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        logger.info("Обробка команди /start для користувача %s.", user.id)
        
        if user.id in ADMIN_IDS:
            # --- ЗМІНА: Використовуємо нову inline-клавіатуру для адміна ---
            await message.answer(
                LEXICON.CMD_START_ADMIN,
                reply_markup=get_admin_main_kb()
            )
            logger.info("Надано адмін-інтерфейс для %s.", user.id)
        else:
            # --- ЗМІНА: Використовуємо нову inline-клавіатуру для користувача ---
            await message.answer(
                LEXICON.CMD_START_USER,
                reply_markup=get_user_main_kb()
            )
            logger.info("Надано звичайний інтерфейс для %s.", user.id)
            
    except Exception as e:
        logger.error("Неочікувана помилка в cmd_start для %s: %s", user.id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR)