import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.orm import orm_get_user_lists_archive
from keyboards.inline import get_archive_kb

router = Router()

@router.message(F.text == "🗂️ Архів списків")
async def show_archive_handler(message: Message):
    """Показує користувачу список його збережених файлів."""
    user_id = message.from_user.id
    logging.info(f"User {user_id} is viewing their archive.")
    archived_lists = await orm_get_user_lists_archive(user_id)

    if not archived_lists:
        await message.answer("У вас ще немає збережених списків.")
        return

    response_text = "🗂️ *Ваш архів списків:*\n\n"
    for i, lst in enumerate(archived_lists, 1):
        created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
        response_text += f"{i}. `{lst.file_name}` (від {created_date})\n"

    await message.answer(response_text, reply_markup=get_archive_kb(user_id))