# epicservice/handlers/archive.py

import logging

# --- ЗМІНА: Додаємо F, CallbackQuery та SQLAlchemyError ---
from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.exc import SQLAlchemyError

from database.orm import orm_get_user_lists_archive
# --- ЗМІНА: Імпортуємо клавіатури, що нам знадобляться ---
from keyboards.inline import get_archive_kb
from lexicon.lexicon import LEXICON
# --- ЗМІНА: Імпортуємо обробник повернення на головне меню ---
from handlers.user.list_management import back_to_main_menu


logger = logging.getLogger(__name__)

router = Router()

# --- ЗМІНА: Обробник тепер реагує на callback, а не на текст ---
@router.callback_query(F.data == "main:archive")
async def show_archive_handler(callback: CallbackQuery):
    """
    Обробник для кнопки '🗂️ Архів списків'.

    Дістає з бази даних усі збережені списки для поточного користувача,
    форматує їх у вигляді нумерованого списку та надсилає користувачу,
    редагуючи повідомлення головного меню.
    """
    user_id = callback.from_user.id
    
    try:
        logger.info("Користувач %s запитує свій архів.", user_id)
        archived_lists = await orm_get_user_lists_archive(user_id)

        # Якщо у користувача ще немає збережених списків
        if not archived_lists:
            # Просто показуємо сповіщення, не змінюючи головне меню
            await callback.answer(LEXICON.NO_ARCHIVED_LISTS, show_alert=True)
            return

        # Формуємо текстове повідомлення зі списком архівів
        response_text = [LEXICON.ARCHIVE_TITLE]
        for i, lst in enumerate(archived_lists, 1):
            # Форматуємо дату для кращого вигляду
            created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
            response_text.append(
                LEXICON.ARCHIVE_ITEM.format(
                    i=i, 
                    file_name=lst.file_name, 
                    created_date=created_date
                )
            )
        
        # Редагуємо повідомлення головного меню, перетворюючи його на екран архіву
        await callback.message.edit_text(
            "\n".join(response_text), 
            reply_markup=get_archive_kb(user_id)
        )
        await callback.answer()
        
    except SQLAlchemyError as e:
        logger.error("Помилка БД при отриманні архіву для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при перегляді архіву %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)