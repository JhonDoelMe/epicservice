import asyncio
import logging
import os
import shutil
import zipfile
from datetime import datetime
from typing import Optional, List, Dict, Any, Set

import pandas as pd
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS, ARCHIVES_PATH
from database.orm import (orm_clear_all_reservations, orm_delete_all_saved_lists_sync,
                         orm_get_all_collected_items_sync, orm_get_all_files_for_user,
                         orm_get_all_products_sync, orm_get_all_temp_list_items_sync,
                         orm_get_user_lists_archive, orm_get_users_with_archives,
                         orm_smart_import)
from keyboards.inline import (get_admin_panel_kb, get_archive_kb,
                             get_confirmation_kb, get_users_with_archives_kb)
from keyboards.reply import admin_main_kb, cancel_kb
from lexicon.lexicon import LEXICON

# Налаштування логування
logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

class AdminStates(StatesGroup):
    waiting_for_import_file = State()
    confirm_delete_all_lists = State()

def _validate_excel_columns(df: pd.DataFrame) -> bool:
    """Перевіряє наявність обов'язкових стовпців у Excel файлі"""
    required_columns = {"в", "г", "н", "к"}
    return required_columns.issubset(set(df.columns))

def _validate_excel_data(df: pd.DataFrame) -> List[str]:
    """Перевіряє коректність даних у Excel файлі"""
    errors = []
    for index, row in df.iterrows():
        if not pd.isna(row["н"]) and (not isinstance(row["в"], (int, float)) or pd.isna(row["в"])):
            errors.append(f"Рядок {index + 2}: 'відділ' має бути числом")
        if len(errors) >= 10:
            errors.append("... та інші помилки")
            break
    return errors

async def _pack_user_files_to_zip(user_id: int) -> Optional[str]:
    """Створює ZIP архів з файлами користувача"""
    try:
        file_paths = await orm_get_all_files_for_user(user_id)
        if not file_paths:
            return None

        zip_filename = f"user_{user_id}_archive_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        zip_path = os.path.join(ARCHIVES_PATH, zip_filename)
        
        os.makedirs(ARCHIVES_PATH, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    zipf.write(file_path, os.path.basename(file_path))
        
        return zip_path
    except Exception as e:
        logger.error("Помилка створення ZIP архіву для %s: %s", user_id, e)
        return None

def _create_stock_report() -> Optional[str]:
    """Генерує звіт про залишки товарів"""
    try:
        products = orm_get_all_products_sync()
        temp_list_items = orm_get_all_temp_list_items_sync()

        temp_reservations = {}
        for item in temp_list_items:
            temp_reservations[item.product_id] = temp_reservations.get(item.product_id, 0) + item.quantity

        report_data = []
        for product in products:
            try:
                stock_qty = float(product.кількість)
            except (ValueError, TypeError):
                stock_qty = 0

            reserved = (product.відкладено or 0) + temp_reservations.get(product.id, 0)
            available = stock_qty - reserved

            report_data.append({
                "Відділ": product.відділ,
                "Група": product.група,
                "Назва": product.назва,
                "Залишок": int(available) if available == int(available) else available,
            })

        df = pd.DataFrame(report_data)
        report_path = os.path.join(ARCHIVES_PATH, f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
        df.to_excel(report_path, index=False)
        return report_path
    except Exception as e:
        logger.error("Помилка створення звіту про залишки: %s", e)
        return None

@router.message(F.text == "👑 Адмін-панель")
async def admin_panel_handler(message: Message):
    """Обробник відкриття адмін-панелі"""
    try:
        await message.answer(
            LEXICON.ADMIN_PANEL_GREETING,
            reply_markup=get_admin_panel_kb()
        )
    except Exception as e:
        logger.error("Помилка відображення адмін-панелі: %s", e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)

@router.callback_query(F.data == "admin:main")
async def admin_panel_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обробник повернення до головного меню адмін-панелі"""
    try:
        if await state.get_state():
            await state.clear()
        await callback.message.edit_text(
            LEXICON.ADMIN_PANEL_GREETING,
            reply_markup=get_admin_panel_kb()
        )
        await callback.answer()
    except Exception as e:
        logger.error("Помилка обробки повернення до адмін-панелі: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.callback_query(F.data == "admin:import_products")
async def start_import_handler(callback: CallbackQuery, state: FSMContext):
    """Ініціалізація процесу імпорту товарів"""
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            LEXICON.IMPORT_PROMPT,
            reply_markup=cancel_kb
        )
        await state.set_state(AdminStates.waiting_for_import_file)
        await callback.answer()
    except Exception as e:
        logger.error("Помилка ініціалізації імпорту: %s", e)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)

@router.message(AdminStates.waiting_for_import_file, F.document)
async def process_import_file(message: Message, state: FSMContext, bot: Bot):
    """Обробка завантаженого файлу для імпорту"""
    admin_id = message.from_user.id
    file_name = message.document.file_name
    
    if not file_name.endswith(".xlsx"):
        await message.answer(LEXICON.IMPORT_WRONG_FORMAT)
        return

    try:
        await message.answer(LEXICON.IMPORT_PROCESSING, reply_markup=admin_main_kb)
        temp_file = f"temp_import_{admin_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        await bot.download(message.document, destination=temp_file)
        logger.info("Адмін %s завантажив файл для імпорту: %s", admin_id, file_name)

        try:
            df = pd.read_excel(temp_file)
            if not _validate_excel_columns(df):
                await message.answer(LEXICON.IMPORT_INVALID_COLUMNS.format(columns=", ".join(df.columns)))
                return

            errors = _validate_excel_data(df)
            if errors:
                error_msg = LEXICON.IMPORT_VALIDATION_ERRORS_TITLE + "\n".join(errors)
                await message.answer(error_msg)
                return

            await message.answer(LEXICON.IMPORT_STARTING)
            await orm_clear_all_reservations()
            
            result = await orm_smart_import(df)
            await message.answer(result)
            
        except Exception as e:
            logger.error("Помилка обробки Excel файлу: %s", e)
            await message.answer(LEXICON.IMPORT_CRITICAL_READ_ERROR.format(error=e))
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
    except Exception as e:
        logger.error("Помилка завантаження файлу: %s", e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)
    finally:
        await state.clear()

@router.message(AdminStates.waiting_for_import_file, F.text == "❌ Скасувати")
async def cancel_import(message: Message, state: FSMContext):
    """Скасування процесу імпорту"""
    logger.info("Адмін %s скасував імпорт", message.from_user.id)
    await state.clear()
    await message.answer(LEXICON.IMPORT_CANCELLED, reply_markup=admin_main_kb)

@router.callback_query(F.data == "admin:user_archives")
async def show_users_archives_list(callback: CallbackQuery):
    """Відображення списку користувачів з архівами"""
    try:
        users = await orm_get_users_with_archives()
        if not users:
            await callback.answer(LEXICON.NO_USERS_WITH_ARCHIVES, show_alert=True)
            return
            
        await callback.message.edit_text(
            LEXICON.CHOOSE_USER_TO_VIEW_ARCHIVE,
            reply_markup=get_users_with_archives_kb(users)
        )
        await callback.answer()
    except SQLAlchemyError as e:
        logger.error("Помилка отримання списку користувачів: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.callback_query(F.data.startswith("admin:view_user:"))
async def view_user_archive(callback: CallbackQuery):
    """Перегляд архіву конкретного користувача"""
    try:
        user_id = int(callback.data.split(":")[-1])
        archived_lists = await orm_get_user_lists_archive(user_id)
        
        if not archived_lists:
            await callback.answer(LEXICON.USER_HAS_NO_ARCHIVES, show_alert=True)
            return

        response = LEXICON.USER_ARCHIVE_TITLE.format(user_id=user_id)
        for i, lst in enumerate(archived_lists, 1):
            created_date = lst.created_at.strftime("%d.%m.%Y о %H:%M")
            response += LEXICON.ARCHIVE_ITEM.format(
                i=i, file_name=lst.file_name, created_date=created_date
            )

        await callback.message.edit_text(
            response,
            reply_markup=get_archive_kb(user_id, is_admin_view=True)
        )
        await callback.answer()
    except ValueError as e:
        logger.error("Невірний ID користувача: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    except SQLAlchemyError as e:
        logger.error("Помилка БД при отриманні архіву: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.callback_query(F.data.startswith("download_zip:"))
async def admin_download_zip_handler(callback: CallbackQuery):
    """Завантаження архіву користувача у форматі ZIP"""
    try:
        user_id = int(callback.data.split(":")[-1])
        await callback.message.edit_text(LEXICON.PACKING_ARCHIVE.format(user_id=user_id))
        
        zip_path = await _pack_user_files_to_zip(user_id)
        if not zip_path:
            await callback.answer(LEXICON.NO_FILES_TO_ARCHIVE, show_alert=True)
            return

        try:
            document = FSInputFile(zip_path)
            await callback.message.answer_document(
                document,
                caption=LEXICON.ZIP_ARCHIVE_CAPTION.format(user_id=user_id)
            )
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)
                
        await callback.answer()
    except Exception as e:
        logger.error("Помилка завантаження ZIP архіву: %s", e)
        await callback.answer(LEXICON.ZIP_ERROR.format(error=e), show_alert=True)

@router.callback_query(F.data == "admin:export_stock")
async def export_stock_handler(callback: CallbackQuery):
    """Експорт звіту про залишки товарів"""
    try:
        await callback.message.edit_text(LEXICON.EXPORTING_STOCK)
        
        report_path = _create_stock_report()
        if not report_path:
            await callback.message.answer(LEXICON.STOCK_REPORT_ERROR)
            return

        try:
            await callback.message.answer_document(
                FSInputFile(report_path),
                caption=LEXICON.STOCK_REPORT_CAPTION
            )
        finally:
            if os.path.exists(report_path):
                os.remove(report_path)
                
        await callback.message.answer(
            LEXICON.ADMIN_PANEL_GREETING,
            reply_markup=get_admin_panel_kb()
        )
        await callback.answer()
    except Exception as e:
        logger.error("Помилка експорту звіту про залишки: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.callback_query(F.data == "admin:delete_all_lists")
async def delete_all_lists_confirm_handler(callback: CallbackQuery, state: FSMContext):
    """Підтвердження видалення всіх списків"""
    try:
        await callback.message.edit_text(
            LEXICON.DELETE_ALL_LISTS_CONFIRM,
            reply_markup=get_confirmation_kb(
                "confirm_delete_all_yes", "confirm_delete_all_no"
            ),
        )
        await state.set_state(AdminStates.confirm_delete_all_lists)
        await callback.answer()
    except Exception as e:
        logger.error("Помилка підтвердження видалення списків: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.callback_query(AdminStates.confirm_delete_all_lists, F.data == "confirm_delete_all_yes")
async def delete_all_lists_confirmed_handler(callback: CallbackQuery, state: FSMContext):
    """Видалення всіх списків після підтвердження"""
    try:
        await state.clear()
        admin_id = callback.from_user.id
        logger.warning("Адмін %s ініціював видалення всіх списків", admin_id)
        
        deleted_count = await asyncio.to_thread(orm_delete_all_saved_lists_sync)
        
        if deleted_count > 0:
            await callback.message.edit_text(
                LEXICON.DELETE_ALL_LISTS_SUCCESS.format(count=deleted_count)
            )
        else:
            await callback.message.edit_text(LEXICON.NO_LISTS_TO_DELETE)

        await callback.message.answer(
            LEXICON.ADMIN_PANEL_GREETING,
            reply_markup=get_admin_panel_kb()
        )
        await callback.answer()
    except Exception as e:
        logger.error("Помилка видалення списків: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.callback_query(AdminStates.confirm_delete_all_lists, F.data == "confirm_delete_all_no")
async def delete_all_lists_cancelled_handler(callback: CallbackQuery, state: FSMContext):
    """Скасування видалення всіх списків"""
    try:
        await state.clear()
        await callback.message.edit_text(LEXICON.DELETE_ALL_LISTS_CANCELLED)
        await callback.message.answer(
            LEXICON.ADMIN_PANEL_GREETING,
            reply_markup=get_admin_panel_kb()
        )
        await callback.answer()
    except Exception as e:
        logger.error("Помилка скасування видалення списків: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)