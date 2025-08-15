# epicservice/handlers/admin/report_handlers.py

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import ADMIN_IDS, ARCHIVES_PATH
from database.orm import (orm_get_all_collected_items_sync,
                          orm_get_all_products_sync,
                          orm_get_all_temp_list_items_sync,
                          orm_get_users_with_active_lists,
                          orm_subtract_collected)
from keyboards.inline import get_admin_lock_kb
from keyboards.reply import admin_main_kb, cancel_kb
from lexicon.lexicon import LEXICON
from utils.force_save_helper import force_save_user_list

# Налаштовуємо логер
logger = logging.getLogger(__name__)

# Створюємо роутер
router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


# Визначаємо стани FSM
class AdminReportStates(StatesGroup):
    waiting_for_subtract_file = State()
    lock_confirmation = State()


# --- Допоміжні функції ---

def _create_stock_report_sync() -> Optional[str]:
    # ... (код залишається без змін)
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
                "Залишок": int(available) if available.is_integer() else available,
            })

        df = pd.DataFrame(report_data)
        os.makedirs(ARCHIVES_PATH, exist_ok=True)
        report_path = os.path.join(ARCHIVES_PATH, f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
        df.to_excel(report_path, index=False)
        return report_path
    except Exception as e:
        logger.error("Помилка створення звіту про залишки: %s", e, exc_info=True)
        return None


def _parse_subtract_file(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    "Розумний" парсер файлу для віднімання.
    Розпізнає два формати: повний звіт та простий (артикул, кількість).
    """
    # Спроба 1: Розпізнати як повний звіт
    full_report_columns = {"Відділ", "Група", "Назва", "Кількість"}
    if full_report_columns.issubset(set(df.columns)):
        df_standardized = df[['Назва', 'Кількість']].copy()
        # Витягуємо артикул з назви
        df_standardized['артикул'] = df_standardized['Назва'].astype(str).str.extract(r'^(\d{8,})')
        df_standardized = df_standardized.dropna(subset=['артикул']) # Видаляємо рядки, де артикул не знайдено
        return df_standardized[['артикул', 'Кількість']]

    # Спроба 2: Розпізнати як простий файл (артикул, кількість)
    if len(df.columns) == 2:
        df_simple = df.copy()
        df_simple.columns = ['артикул', 'Кількість'] # Перейменовуємо колонки
        # Перевіряємо, що в першій колонці дійсно артикули
        if df_simple['артикул'].astype(str).str.match(r'^\d{8,}$').all():
            return df_simple

    return None # Якщо жоден формат не підійшов


async def proceed_with_stock_export(callback: CallbackQuery):
    # ... (код залишається без змін)
    await callback.message.edit_text(LEXICON.EXPORTING_STOCK)
    loop = asyncio.get_running_loop()
    report_path = await loop.run_in_executor(None, _create_stock_report_sync)
    if not report_path:
        await callback.message.edit_text(LEXICON.STOCK_REPORT_ERROR)
        await callback.answer()
        return
    try:
        await callback.message.answer_document(FSInputFile(report_path), caption=LEXICON.STOCK_REPORT_CAPTION)
    finally:
        if os.path.exists(report_path):
            os.remove(report_path)
    await callback.message.delete()
    await callback.answer()


async def proceed_with_collected_export(callback: CallbackQuery):
    # ... (код залишається без змін)
    await callback.message.edit_text(LEXICON.COLLECTED_REPORT_PROCESSING)
    loop = asyncio.get_running_loop()
    try:
        collected_items = await loop.run_in_executor(None, orm_get_all_collected_items_sync)
        if not collected_items:
            await callback.message.edit_text(LEXICON.COLLECTED_REPORT_EMPTY)
            await callback.answer()
            return
        df = pd.DataFrame(collected_items)
        df.rename(columns={"department": "Відділ", "group": "Група", "name": "Назва", "quantity": "Кількість"}, inplace=True)
        os.makedirs(ARCHIVES_PATH, exist_ok=True)
        report_path = os.path.join(ARCHIVES_PATH, f"collected_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
        df.to_excel(report_path, index=False)
        await callback.message.answer_document(FSInputFile(report_path), caption=LEXICON.COLLECTED_REPORT_CAPTION)
        os.remove(report_path)
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        logger.error("Помилка створення зведеного звіту: %s", e, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
        await callback.answer()


# --- Обробники експорту звітів з механізмом блокування ---

@router.callback_query(F.data == "admin:export_stock")
async def export_stock_handler(callback: CallbackQuery, state: FSMContext):
    # ... (код залишається без змін)
    active_users = await orm_get_users_with_active_lists()
    if not active_users:
        await proceed_with_stock_export(callback)
        return
    users_info = "\n".join([f"- Користувач `{user_id}` (позицій: {count})" for user_id, count in active_users])
    await state.update_data(action_to_perform='export_stock', locked_user_ids=[uid for uid, _ in active_users])
    await state.set_state(AdminReportStates.lock_confirmation)
    await callback.message.edit_text(LEXICON.ACTIVE_LISTS_BLOCK.format(users_info=users_info), reply_markup=get_admin_lock_kb('export_stock'))
    await callback.answer("Дію заблоковано", show_alert=True)


@router.callback_query(F.data == "admin:export_collected")
async def export_collected_handler(callback: CallbackQuery, state: FSMContext):
    # ... (код залишається без змін)
    active_users = await orm_get_users_with_active_lists()
    if not active_users:
        await proceed_with_collected_export(callback)
        return
    users_info = "\n".join([f"- Користувач `{user_id}` (позицій: {count})" for user_id, count in active_users])
    await state.update_data(action_to_perform='export_collected', locked_user_ids=[uid for uid, _ in active_users])
    await state.set_state(AdminReportStates.lock_confirmation)
    await callback.message.edit_text(LEXICON.ACTIVE_LISTS_BLOCK.format(users_info=users_info), reply_markup=get_admin_lock_kb('export_collected'))
    await callback.answer("Дію заблоковано", show_alert=True)


# --- Обробники кнопок блокування ---

@router.callback_query(AdminReportStates.lock_confirmation, F.data.startswith("lock:notify:"))
async def handle_report_lock_notify(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код залишається без змін)
    data = await state.get_data()
    for user_id in data.get('locked_user_ids', []):
        try:
            await bot.send_message(user_id, LEXICON.USER_SAVE_LIST_NOTIFICATION)
        except Exception as e:
            logger.warning("Не вдалося надіслати сповіщення користувачу %s: %s", user_id, e)
    await callback.answer(LEXICON.NOTIFICATIONS_SENT, show_alert=True)


@router.callback_query(AdminReportStates.lock_confirmation, F.data.startswith("lock:force_save:"))
async def handle_report_lock_force_save(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код залишається без змін)
    await callback.message.edit_text("Почав примусове збереження списків...")
    data = await state.get_data()
    user_ids, action = data.get('locked_user_ids', []), data.get('action_to_perform')
    all_saved_successfully = all([await force_save_user_list(user_id, bot) for user_id in user_ids])
    if not all_saved_successfully:
        await callback.message.edit_text("Під час примусового збереження виникли помилки. Спробуйте пізніше.")
        await state.clear()
        return
    await callback.answer("Всі списки успішно збережено!", show_alert=True)
    if action == 'export_stock':
        await proceed_with_stock_export(callback)
    elif action == 'export_collected':
        await proceed_with_collected_export(callback)
    await state.clear()


# --- Сценарій віднімання зібраного ---

@router.callback_query(F.data == "admin:subtract_collected")
async def start_subtract_handler(callback: CallbackQuery, state: FSMContext):
    # ... (код залишається без змін)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(LEXICON.SUBTRACT_PROMPT, reply_markup=cancel_kb)
    await state.set_state(AdminReportStates.waiting_for_subtract_file)
    await callback.answer()


@router.message(AdminReportStates.waiting_for_subtract_file, F.document)
async def process_subtract_file(message: Message, state: FSMContext, bot: Bot):
    if not message.document.file_name.endswith((".xlsx", ".csv")):
        await message.answer(LEXICON.IMPORT_WRONG_FORMAT)
        return
    await state.clear()
    await message.answer(LEXICON.SUBTRACT_PROCESSING, reply_markup=admin_main_kb)
    temp_file_path = f"temp_subtract_{message.from_user.id}.tmp"
    try:
        await bot.download(message.document, destination=temp_file_path)
        
        # Використовуємо pd.read_excel для .xlsx і pd.read_csv для .csv
        if message.document.file_name.endswith(".xlsx"):
            df = await asyncio.to_thread(pd.read_excel, temp_file_path)
        else:
            df = await asyncio.to_thread(pd.read_csv, temp_file_path)

        # ВИПРАВЛЕНО: Використовуємо новий "розумний" парсер
        standardized_df = _parse_subtract_file(df)
        
        if standardized_df is None:
            await message.answer(LEXICON.SUBTRACT_INVALID_COLUMNS.format(columns=", ".join(df.columns)))
            return

        result = await orm_subtract_collected(standardized_df)
        report_text = "\n".join([
            LEXICON.SUBTRACT_REPORT_TITLE,
            LEXICON.SUBTRACT_REPORT_PROCESSED.format(processed=result['processed']),
            LEXICON.SUBTRACT_REPORT_NOT_FOUND.format(not_found=result['not_found']),
            LEXICON.SUBTRACT_REPORT_ERROR.format(errors=result['errors']),
        ])
        await message.answer(report_text)
    except Exception as e:
        logger.error("Помилка обробки файлу для віднімання: %s", e, exc_info=True)
        await message.answer(LEXICON.IMPORT_CRITICAL_READ_ERROR.format(error=e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        await state.clear()


@router.message(AdminReportStates.waiting_for_subtract_file, F.text == "❌ Скасувати")
async def cancel_subtract(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(LEXICON.ACTION_CANCELED, reply_markup=admin_main_kb)