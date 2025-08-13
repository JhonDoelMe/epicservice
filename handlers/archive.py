import logging
from typing import List

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.exc import SQLAlchemyError

from database.orm import orm_get_user_lists_archive
from keyboards.inline import get_archive_kb
from lexicon.lexicon import LEXICON

# Налаштування логування
logger = logging.getLogger(__name__)

router = Router()

@router.message(F.text == "🗂️ Архів списків")
async def show_archive_handler(message: Message) -> None:
    """
    Відображає користувачу його збережені списки товарів.
    
    Args:
        message: Об'єкт повідомлення від користувача
    """
    user_id = message.from_user.id
    
    try:
        logger.info("Користувач %s переглядає свій архів", user_id)
        archived_lists = await orm_get_user_lists_archive(user_id)

        if not archived_lists:
            await message.answer(LEXICON.NO_ARCHIVED_LISTS)
            return

        response_text = LEXICON.ARCHIVE_TITLE
        for i, lst in enumerate(archived_lists, 1):
            created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
            response_text += LEXICON.ARCHIVE_ITEM.format(
                i=i, 
                file_name=lst.file_name, 
                created_date=created_date
            )

        await message.answer(response_text, reply_markup=get_archive_kb(user_id))
        
    except SQLAlchemyError as e:
        logger.error("Помилка БД при отриманні архіву для %s: %s", user_id, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при перегляді архіву %s: %s", user_id, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)