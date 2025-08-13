import asyncio
import logging
import os
import zipfile
from datetime import datetime

import pandas as pd
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import ADMIN_IDS, ARCHIVES_PATH
from database.orm import (orm_clear_all_reservations, orm_get_all_files_for_user,
                          orm_get_all_products_sync,
                          orm_get_all_temp_list_items_sync,
                          orm_get_user_lists_archive,
                          orm_get_users_with_archives, orm_smart_import,
                          orm_get_all_collected_items_sync)
from keyboards.inline import (get_admin_panel_kb, get_archive_kb,
                              get_users_with_archives_kb)
from keyboards.reply import admin_main_kb, cancel_kb
from lexicon.lexicon import LEXICON

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminStates(StatesGroup):
    waiting_for_import_file = State()


@router.message(F.text == "👑 Адмін-панель")
async def admin_panel_handler(message: Message):
    await message.answer(LEXICON.ADMIN_PANEL_GREETING, reply_markup=get_admin_panel_kb())


@router.callback_query(F.data == "admin:main")
async def admin_panel_callback_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        LEXICON.ADMIN_PANEL_GREETING, reply_markup=get_admin_panel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:import_products")
async def start_import_handler(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} initiated product import.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(LEXICON.IMPORT_PROMPT, reply_markup=cancel_kb)
    await state.set_state(AdminStates.waiting_for_import_file)
    await callback.answer()


@router.message(AdminStates.waiting_for_import_file, F.document)
async def process_import_file(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    file_name = message.document.file_name
    if not file_name.endswith(".xlsx"):
        await message.answer(LEXICON.IMPORT_WRONG_FORMAT)
        return

    await message.answer(LEXICON.IMPORT_PROCESSING, reply_markup=admin_main_kb)
    file_path = f"temp_{message.document.file_id}.xlsx"
    await bot.download(message.document, destination=file_path)
    logging.info(f"Admin {admin_id} uploaded file '{file_name}' for import.")

    try:
        df = pd.read_excel(file_path)
        expected_columns = ["в", "г", "н", "к"]
        if list(df.columns) != expected_columns:
            error_msg = LEXICON.IMPORT_INVALID_COLUMNS.format(
                columns=", ".join(df.columns)
            )
            logging.warning(f"Admin {admin_id} failed import: {error_msg}")
            await message.answer(error_msg)
            os.remove(file_path)
            await state.clear()
            return

        errors = []
        for index, row in df.iterrows():
            if not pd.isna(row["н"]) and (
                not isinstance(row["в"], (int, float)) or pd.isna(row["в"])
            ):
                errors.append(f"Рядок {index + 2}: 'відділ' має бути числом.")
            if len(errors) > 10:
                errors.append("... та багато інших помилок.")
                break

        if errors:
            error_msg = LEXICON.IMPORT_VALIDATION_ERRORS_TITLE + "\n".join(errors)
            logging.warning(f"Admin {admin_id} failed import due to validation errors.")
            await message.answer(error_msg)
            os.remove(file_path)
            await state.clear()
            return

    except Exception as e:
        logging.error(f"Admin {admin_id} failed import on file read: {e}")
        await message.answer(LEXICON.IMPORT_CRITICAL_READ_ERROR.format(error=e))
        if os.path.exists(file_path):
            os.remove(file_path)
        await state.clear()
        return

    await message.answer(LEXICON.IMPORT_STARTING)
    await orm_clear_all_reservations()
    logging.info(f"Admin {admin_id}: All reservations cleared before import.")

    result_message = await orm_smart_import(df)
    log_message = result_message.replace("\n", " ")
    logging.info(f"Admin {admin_id}: Import finished. Result: {log_message}")

    await message.answer(result_message)
    await state.clear()

    if os.path.exists(file_path):
        os.remove(file_path)


@router.message(AdminStates.waiting_for_import_file, F.text == "❌ Скасувати")
async def cancel_import(message: Message, state: FSMContext):
    logging.info(f"Admin {message.from_user.id} cancelled the import process.")
    await state.clear()
    await message.answer(LEXICON.IMPORT_CANCELLED, reply_markup=admin_main_kb)


@router.message(AdminStates.waiting_for_import_file)
async def incorrect_import_file(message: Message):
    await message.answer(LEXICON.IMPORT_INCORRECT_FILE)


@router.callback_query(F.data == "admin:user_archives")
async def show_users_archives_list(callback: CallbackQuery):
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} is viewing the list of users with archives.")
    users = await orm_get_users_with_archives()
    if not users:
        await callback.answer(LEXICON.NO_USERS_WITH_ARCHIVES, show_alert=True)
        return
    await callback.message.edit_text(
        LEXICON.CHOOSE_USER_TO_VIEW_ARCHIVE,
        reply_markup=get_users_with_archives_kb(users),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:view_user:"))
async def view_user_archive(callback: CallbackQuery):
    admin_id = callback.from_user.id
    user_id = int(callback.data.split(":")[-1])
    logging.info(f"Admin {admin_id} is viewing the archive of user {user_id}.")
    archived_lists = await orm_get_user_lists_archive(user_id)
    if not archived_lists:
        await callback.answer(LEXICON.USER_HAS_NO_ARCHIVES, show_alert=True)
        return

    response_text = LEXICON.USER_ARCHIVE_TITLE.format(user_id=user_id)
    for i, lst in enumerate(archived_lists, 1):
        created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
        response_text += LEXICON.ARCHIVE_ITEM.format(
            i=i, file_name=lst.file_name, created_date=created_date
        )

    await callback.message.edit_text(
        response_text, reply_markup=get_archive_kb(user_id, is_admin_view=True)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("download_zip:"))
async def admin_download_zip_handler(callback: CallbackQuery):
    admin_id = callback.from_user.id
    user_id = int(callback.data.split(":")[-1])
    logging.info(f"Admin {admin_id} initiated ZIP download for user {user_id}.")
    file_paths = await orm_get_all_files_for_user(user_id)
    if not file_paths:
        await callback.answer(LEXICON.NO_FILES_TO_ARCHIVE, show_alert=True)
        return

    await callback.message.edit_text(LEXICON.PACKING_ARCHIVE.format(user_id=user_id))
    zip_path = os.path.join(ARCHIVES_PATH, f"admin_view_user_{user_id}_archive.zip")
    os.makedirs(ARCHIVES_PATH, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "w") as zf:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    zf.write(file_path, arcname=os.path.basename(file_path))
        document = FSInputFile(zip_path)
        await callback.message.answer_document(
            document, caption=LEXICON.ZIP_ARCHIVE_CAPTION.format(user_id=user_id)
        )
        logging.info(f"Admin {admin_id} successfully downloaded ZIP for user {user_id}.")
    except Exception as e:
        logging.error(f"Error creating ZIP for admin {admin_id}, user {user_id}: {e}")
        await callback.message.answer(LEXICON.ZIP_ERROR.format(error=e))
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    await callback.answer()


def _sync_export_stock():
    products = orm_get_all_products_sync()
    temp_list_items = orm_get_all_temp_list_items_sync()

    temp_reservations = {}
    for item in temp_list_items:
        temp_reservations[item.product_id] = temp_reservations.get(
            item.product_id, 0
        ) + item.quantity

    export_data = []
    for product in products:
        try:
            stock_quantity = float(product.кількість)
        except (ValueError, TypeError):
            stock_quantity = 0

        permanently_reserved = product.відкладено or 0
        temporarily_reserved = temp_reservations.get(product.id, 0)
        final_stock = stock_quantity - permanently_reserved - temporarily_reserved

        export_data.append(
            {
                "Відділ": product.відділ,
                "Група": product.група,
                "Назва": product.назва,
                "Залишок": final_stock,
            }
        )

    df = pd.DataFrame(export_data)
    df["Залишок"] = df["Залишок"].apply(lambda x: int(x) if x == int(x) else x)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_name = f"stock_balance_{timestamp}.xlsx"
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file_name)

    df.to_excel(file_path, index=False)
    return file_path


@router.callback_query(F.data == "admin:export_stock")
async def export_stock_handler(callback: CallbackQuery):
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} initiated stock balance export.")
    await callback.message.edit_text(LEXICON.EXPORTING_STOCK)

    loop = asyncio.get_running_loop()
    file_path = await loop.run_in_executor(None, _sync_export_stock)

    if file_path and os.path.exists(file_path):
        document = FSInputFile(file_path)
        await callback.message.answer_document(document, caption=LEXICON.STOCK_REPORT_CAPTION)
        logging.info(f"Admin {admin_id} successfully exported stock balance.")
        os.remove(file_path)
    else:
        logging.error(f"Failed to create stock balance report for admin {admin_id}.")
        await callback.message.answer(LEXICON.STOCK_REPORT_ERROR)

    await callback.message.answer(
        LEXICON.ADMIN_PANEL_GREETING, reply_markup=get_admin_panel_kb()
    )
    await callback.answer()


def _sync_export_collected_report():
    collected_items = orm_get_all_collected_items_sync()
    if not collected_items:
        return None

    sorted_items = sorted(collected_items, key=lambda x: (x['department'], x['group'], x['name']))
    
    export_data = [{
        'Відділ': item['department'],
        'Група': item['group'],
        'Назва': item['name'],
        'Зібрано (кількість)': item['quantity']
    } for item in sorted_items]
    
    df = pd.DataFrame(export_data)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_name = f"collected_summary_{timestamp}.xlsx"
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file_name)
    
    df.to_excel(file_path, index=False)
    return file_path


@router.callback_query(F.data == "admin:export_collected")
async def export_collected_handler(callback: CallbackQuery):
    admin_id = callback.from_user.id
    logging.info(f"Admin {admin_id} initiated collected items summary export.")
    await callback.message.edit_text(LEXICON.COLLECTED_REPORT_PROCESSING)
    
    loop = asyncio.get_running_loop()
    file_path = await loop.run_in_executor(None, _sync_export_collected_report)

    if file_path and os.path.exists(file_path):
        document = FSInputFile(file_path)
        await callback.message.answer_document(document, caption=LEXICON.COLLECTED_REPORT_CAPTION)
        logging.info(f"Admin {admin_id} successfully exported collected items summary.")
        os.remove(file_path)
    else:
        logging.warning(f"No collected items found for admin {admin_id} report.")
        await callback.message.answer(LEXICON.COLLECTED_REPORT_EMPTY)
        
    await callback.message.answer(
        LEXICON.ADMIN_PANEL_GREETING, reply_markup=get_admin_panel_kb()
    )
    await callback.answer()