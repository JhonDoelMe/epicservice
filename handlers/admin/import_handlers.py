# epicservice/handlers/admin/import_handlers.py

import asyncio
import logging
import os
from typing import List

import pandas as pd
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, Message,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS
from database.orm import (orm_get_all_users_sync,
                          orm_get_users_with_active_lists, orm_smart_import)
from handlers.admin.core import _show_admin_panel
# --- ВИПРАВЛЕНО: Додано get_admin_main_kb до імпортів ---
from keyboards.inline import (get_admin_lock_kb, get_notify_confirmation_kb,
                              get_admin_panel_kb, get_user_main_kb, get_admin_main_kb)
from lexicon.lexicon import LEXICON
from utils.force_save_helper import force_save_user_list

# Налаштовуємо логер
logger = logging.getLogger(__name__)

# Створюємо роутер
router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminImportStates(StatesGroup):
    waiting_for_import_file = State()
    lock_confirmation = State()
    notify_confirmation = State()


def _validate_excel_columns(df: pd.DataFrame) -> bool:
    # ... (код без змін)
    required_columns = {"в", "г", "н", "к"}
    return required_columns.issubset(set(df.columns))

def _validate_excel_data(df: pd.DataFrame) -> List[str]:
    # ... (код без змін)
    errors = []
    for index, row in df.iterrows():
        if pd.notna(row["н"]) and not isinstance(row.get("в"), (int, float)):
            errors.append(f"Рядок {index + 2}: 'відділ' має бути числом, а не '{row.get('в')}'")
        if len(errors) >= 10:
            errors.append("... та інші помилки.")
            break
    return errors

def _format_admin_report(result: dict) -> str:
    # ... (код без змін)
    report_lines = [
        LEXICON.IMPORT_REPORT_TITLE,
        LEXICON.IMPORT_REPORT_ADDED.format(added=result['added']),
        LEXICON.IMPORT_REPORT_UPDATED.format(updated=result['updated']),
        LEXICON.IMPORT_REPORT_DELETED.format(deleted=result['deleted']),
        LEXICON.IMPORT_REPORT_TOTAL.format(total=result['total_in_db']),
    ]
    if result['total_in_db'] == result['total_in_file']:
        report_lines.append(LEXICON.IMPORT_REPORT_SUCCESS_CHECK.format(count=result['total_in_file']))
    else:
        report_lines.append(LEXICON.IMPORT_REPORT_FAIL_CHECK.format(db_count=result['total_in_db'], file_count=result['total_in_file']))
    return "\n".join(report_lines)

async def broadcast_import_update(bot: Bot, result: dict):
    # ... (код без змін)
    loop = asyncio.get_running_loop()
    try:
        user_ids = await loop.run_in_executor(None, orm_get_all_users_sync)
        if not user_ids:
            logger.info("Користувачі для розсилки сповіщень про імпорт не знайдені.")
            return

        stats_part = LEXICON.USER_IMPORT_NOTIFICATION_STATS.format(
            added=result['added'], updated=result['updated'], deleted=result['deleted']
        )
        departments_part = LEXICON.USER_IMPORT_NOTIFICATION_DEPARTMENTS_TITLE
        dep_stats = result.get('department_stats', {})
        sorted_deps = sorted(dep_stats.items())
        
        departments_lines = [
            LEXICON.USER_IMPORT_NOTIFICATION_DEPARTMENT_ITEM.format(dep_id=dep_id, count=count)
            for dep_id, count in sorted_deps
        ]
        
        message_text = (
            LEXICON.USER_IMPORT_NOTIFICATION_TITLE + stats_part + "\n" +
            departments_part + "\n".join(departments_lines)
        )

        sent_count = 0
        for user_id in user_ids:
            try:
                # Тепер цей рядок не буде викликати помилку
                kb = get_admin_main_kb() if user_id in ADMIN_IDS else get_user_main_kb()
                
                await bot.send_message(user_id, message_text, reply_markup=kb)
                sent_count += 1
            except Exception as e:
                logger.warning("Не вдалося надіслати сповіщення про імпорт користувачу %s: %s", user_id, e)
        
        logger.info(f"Розсилку про імпорт завершено. Надіслано {sent_count}/{len(user_ids)} повідомлень.")

    except Exception as e:
        logger.error("Критична помилка під час розсилки сповіщень про імпорт: %s", e, exc_info=True)


async def proceed_with_import(message: Message, state: FSMContext, is_after_force_save: bool = False):
    # ... (код без змін)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=LEXICON.BUTTON_BACK_TO_ADMIN_PANEL, 
            callback_data="admin:main"
        )
    ]])
    
    text_to_send = LEXICON.IMPORT_PROMPT
    if is_after_force_save:
        await message.answer(text_to_send, reply_markup=back_kb)
    else:
        await message.edit_text(text_to_send, reply_markup=back_kb)
        
    await state.set_state(AdminImportStates.waiting_for_import_file)


@router.callback_query(F.data == "admin:import_products")
async def start_import_handler(callback: CallbackQuery, state: FSMContext):
    # ... (код без змін)
    active_users = await orm_get_users_with_active_lists()
    if not active_users:
        await proceed_with_import(callback.message, state)
        await callback.answer()
        return
    users_info = "\n".join([f"- Користувач `{user_id}` (позицій: {count})" for user_id, count in active_users])
    await state.update_data(action_to_perform='import', locked_user_ids=[uid for uid, _ in active_users])
    await state.set_state(AdminImportStates.lock_confirmation)
    await callback.message.edit_text(
        LEXICON.ACTIVE_LISTS_BLOCK.format(users_info=users_info),
        reply_markup=get_admin_lock_kb(action='import')
    )
    await callback.answer("Дію заблоковано", show_alert=True)


@router.callback_query(AdminImportStates.lock_confirmation, F.data.startswith("lock:notify:"))
async def handle_lock_notify(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код без змін)
    data = await state.get_data()
    for user_id in data.get('locked_user_ids', []):
        try:
            await bot.send_message(user_id, LEXICON.USER_SAVE_LIST_NOTIFICATION)
        except Exception as e:
            logger.warning("Не вдалося надіслати сповіщення користувачу %s: %s", user_id, e)
    await callback.answer(LEXICON.NOTIFICATIONS_SENT, show_alert=True)


@router.callback_query(AdminImportStates.lock_confirmation, F.data.startswith("lock:force_save:"))
async def handle_lock_force_save(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код без змін)
    await callback.message.edit_text("Почав примусове збереження списків...")
    data = await state.get_data()
    user_ids, action = data.get('locked_user_ids', []), data.get('action_to_perform')
    all_saved_successfully = all([await force_save_user_list(user_id, bot) for user_id in user_ids])
    if not all_saved_successfully:
        await callback.message.edit_text("Під час примусового збереження виникли помилки. Спробуйте пізніше.")
        await state.clear()
        return
    await callback.answer("Всі списки успішно збережено!", show_alert=True)
    if action == 'import':
        await proceed_with_import(callback.message, state, is_after_force_save=True)


@router.message(AdminImportStates.waiting_for_import_file, F.document)
async def process_import_file(message: Message, state: FSMContext, bot: Bot):
    # ... (код без змін)
    if not message.document.file_name.endswith(".xlsx"):
        await message.answer(LEXICON.IMPORT_WRONG_FORMAT)
        return
    
    await bot.delete_message(message.chat.id, message.message_id - 1)
    await message.answer(LEXICON.IMPORT_PROCESSING)
    temp_file_path = f"temp_import_{message.from_user.id}.xlsx"

    try:
        await bot.download(message.document, destination=temp_file_path)
        df = await asyncio.to_thread(pd.read_excel, temp_file_path)

        if not _validate_excel_columns(df):
            await message.answer(LEXICON.IMPORT_INVALID_COLUMNS.format(columns=", ".join(df.columns)))
            return
        errors = _validate_excel_data(df)
        if errors:
            await message.answer(LEXICON.IMPORT_VALIDATION_ERRORS_TITLE + "\n".join(errors))
            return

        await message.answer(LEXICON.IMPORT_STARTING)
        result = await orm_smart_import(df)
        if not result:
            await message.answer(LEXICON.IMPORT_SYNC_ERROR.format(error="невідома помилка."))
            return
        
        admin_report = _format_admin_report(result)
        await message.answer(admin_report)
        
        await state.update_data(import_result=result)
        await message.answer(
            LEXICON.IMPORT_ASK_FOR_NOTIFICATION,
            reply_markup=get_notify_confirmation_kb()
        )
        await state.set_state(AdminImportStates.notify_confirmation)

    except SQLAlchemyError as e:
        logger.critical("Помилка БД під час імпорту: %s", e, exc_info=True)
        await message.answer(LEXICON.IMPORT_SYNC_ERROR.format(error=str(e)))
        await _show_admin_panel(message)
    except Exception as e:
        logger.error("Критична помилка при обробці файлу імпорту: %s", e, exc_info=True)
        await message.answer(LEXICON.IMPORT_CRITICAL_READ_ERROR.format(error=str(e)))
        await _show_admin_panel(message)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.callback_query(AdminImportStates.notify_confirmation, F.data == "notify_confirm:yes")
async def handle_notify_yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код без змін)
    await callback.message.edit_text(LEXICON.BROADCAST_STARTING)
    data = await state.get_data()
    await state.clear()
    
    if result := data.get('import_result'):
        asyncio.create_task(broadcast_import_update(bot, result))
    
    await _show_admin_panel(callback)
    await callback.answer()


@router.callback_query(AdminImportStates.notify_confirmation, F.data == "notify_confirm:no")
async def handle_notify_no(callback: CallbackQuery, state: FSMContext):
    # ... (код без змін)
    await callback.message.edit_text(LEXICON.BROADCAST_SKIPPED)
    await state.clear()
    
    await _show_admin_panel(callback)
    await callback.answer()