import os
import zipfile
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import MagicData

from database.orm import orm_get_user_lists_archive, orm_get_all_files_for_user
from keyboards.inline import get_archive_kb

router = Router()

@router.message(F.text == "🗂️ Архів списків")
async def show_archive_handler(message: Message):
    """Показує користувачу список його збережених файлів."""
    user_id = message.from_user.id
    archived_lists = await orm_get_user_lists_archive(user_id)

    if not archived_lists:
        await message.answer("У вас ще немає збережених списків.")
        return

    response_text = "🗂️ *Ваш архів списків:*\n\n"
    for i, lst in enumerate(archived_lists, 1):
        # Форматуємо дату для гарного вигляду
        created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
        response_text += f"{i}. `{lst.file_name}` (від {created_date})\n"

    await message.answer(response_text, reply_markup=get_archive_kb())

@router.callback_query(F.data == "download_all_zip")
async def download_all_zip_handler(callback: CallbackQuery):
    """Пакує всі файли користувача в ZIP-архів і відправляє його."""
    user_id = callback.from_user.id
    file_paths = await orm_get_all_files_for_user(user_id)

    if not file_paths:
        await callback.answer("Немає файлів для архівації.", show_alert=True)
        return

    await callback.message.edit_text("Почав пакування архівів... Це може зайняти деякий час.")

    zip_path = f"archives/user_{user_id}_archive.zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    # Додаємо файл в архів, зберігаючи тільки його назву
                    zf.write(file_path, arcname=os.path.basename(file_path))
        
        document = FSInputFile(zip_path)
        await callback.message.answer_document(document, caption="Ваш ZIP-архів з усіма списками.")

    except Exception as e:
        await callback.message.answer(f"Сталася помилка при створенні архіву: {e}")
    finally:
        # Видаляємо тимчасовий ZIP-файл
        if os.path.exists(zip_path):
            os.remove(zip_path)

    await callback.answer()