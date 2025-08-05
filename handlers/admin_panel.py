import os
import zipfile
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from keyboards.inline import get_admin_panel_kb, get_users_with_archives_kb, get_archive_kb
from database.orm import orm_smart_import, orm_clear_all_reservations, orm_get_users_with_archives, orm_get_user_lists_archive, orm_get_all_files_for_user

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

class AdminStates(StatesGroup):
    waiting_for_import_file = State()

@router.message(F.text == "👑 Адмін-панель")
async def admin_panel_handler(message: Message):
    await message.answer("Ви в панелі адміністратора. Оберіть дію:", reply_markup=get_admin_panel_kb())

@router.callback_query(F.data == "admin:main")
async def admin_panel_callback_handler(callback: CallbackQuery):
    await callback.message.edit_text("Ви в панелі адміністратора. Оберіть дію:", reply_markup=get_admin_panel_kb())
    await callback.answer()

# --- Логіка імпорту (без змін) ---
@router.callback_query(F.data == "admin:import_products")
async def start_import_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Будь ласка, надішліть мені файл Excel (`.xlsx`) з товарами.")
    await state.set_state(AdminStates.waiting_for_import_file)
    await callback.answer()

@router.message(AdminStates.waiting_for_import_file, F.document)
async def process_import_file(message: Message, state: FSMContext, bot: Bot):
    if not message.document.file_name.endswith('.xlsx'):
        await message.answer("Помилка. Будь ласка, надішліть файл у форматі `.xlsx`.")
        return
    await message.answer("Обробляю файл...")
    await orm_clear_all_reservations()
    file_path = f"temp_{message.document.file_id}.xlsx"
    await bot.download(message.document, destination=file_path)
    result_message = await orm_smart_import(file_path)
    await message.answer(result_message)
    await state.clear()
    if os.path.exists(file_path):
        os.remove(file_path)

@router.message(AdminStates.waiting_for_import_file)
async def incorrect_import_file(message: Message):
    await message.answer("Будь ласка, надішліть документ (файл Excel).")

# --- НОВА ЛОГІКА ДЛЯ ПЕРЕГЛЯДУ АРХІВІВ ---
@router.callback_query(F.data == "admin:user_archives")
async def show_users_archives_list(callback: CallbackQuery):
    users = await orm_get_users_with_archives()
    if not users:
        await callback.answer("Жоден користувач ще не зберіг списку.", show_alert=True)
        return
    await callback.message.edit_text("Оберіть користувача для перегляду його архіву:", reply_markup=get_users_with_archives_kb(users))
    await callback.answer()

@router.callback_query(F.data.startswith("admin:view_user:"))
async def view_user_archive(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[-1])
    archived_lists = await orm_get_user_lists_archive(user_id)
    if not archived_lists:
        await callback.answer("У цього користувача немає збережених списків.", show_alert=True)
        return
    
    response_text = f"🗂️ *Архів користувача `{user_id}`:*\n\n"
    for i, lst in enumerate(archived_lists, 1):
        created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
        response_text += f"{i}. `{lst.file_name}` (від {created_date})\n"
        
    await callback.message.edit_text(response_text, reply_markup=get_archive_kb(user_id, is_admin_view=True))
    await callback.answer()

@router.callback_query(F.data.startswith("download_zip:"))
async def admin_download_zip_handler(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[-1])
    file_paths = await orm_get_all_files_for_user(user_id)
    if not file_paths:
        await callback.answer("Немає файлів для архівації.", show_alert=True)
        return

    await callback.message.edit_text(f"Почав пакування архівів для користувача `{user_id}`...")
    zip_path = f"archives/admin_view_user_{user_id}_archive.zip"
    try:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    zf.write(file_path, arcname=os.path.basename(file_path))
        document = FSInputFile(zip_path)
        await callback.message.answer_document(document, caption=f"ZIP-архів для користувача `{user_id}`.")
    except Exception as e:
        await callback.message.answer(f"Сталася помилка: {e}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    await callback.answer()