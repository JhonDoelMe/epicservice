# epicservice/handlers/user/list_saving.py

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
# --- ЗМІНА: Додаємо Bot та імпорти для клавіатур ---
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS, ARCHIVES_PATH
from database.engine import async_session
from database.orm import (orm_add_saved_list, orm_clear_temp_list,
                          orm_get_product_by_id, orm_get_temp_list,
                          orm_update_reserved_quantity)
# --- ЗМІНА: Імпортуємо клавіатури головного меню ---
from keyboards.inline import get_admin_main_kb, get_user_main_kb
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)
router = Router()

async def _save_list_to_excel(
    items: List[Dict[str, Any]],
    user_id: int,
    prefix: str = ""
) -> Optional[str]:
    # ... (код без змін)
    if not items:
        return None
    try:
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
        first_article = items[0]['артикул']
        file_name = f"{prefix}{first_article}_{timestamp}.xlsx"
        archive_dir = os.path.join(ARCHIVES_PATH, f"user_{user_id}")
        os.makedirs(archive_dir, exist_ok=True)
        file_path = os.path.join(archive_dir, file_name)
        df = pd.DataFrame(items)
        df.to_excel(file_path, index=False, header=['Артикул', 'Кількість'])
        logger.info("Файл успішно збережено: %s", file_path)
        return file_path
    except Exception as e:
        logger.error("Помилка збереження Excel файлу для користувача %s: %s", user_id, e, exc_info=True)
        return None


@router.callback_query(F.data == "save_list")
async def save_list_callback(callback: CallbackQuery, bot: Bot): # Додаємо bot
    user_id = callback.from_user.id
    await callback.message.edit_text(LEXICON.SAVING_LIST_PROCESS)
    try:
        async with async_session() as session:
            async with session.begin():
                temp_list = await orm_get_temp_list(user_id)
                if not temp_list:
                    await callback.message.edit_text(LEXICON.EMPTY_LIST)
                    return

                in_stock_items, surplus_items, reservation_updates = [], [], []

                for item in temp_list:
                    product = await orm_get_product_by_id(session, item.product_id, for_update=True)
                    if not product:
                        continue

                    try:
                        stock_qty = float(str(product.кількість).replace(',', '.'))
                    except (ValueError, TypeError):
                        stock_qty = 0

                    available = stock_qty - (product.відкладено or 0)
                    item_for_excel = {"артикул": product.артикул, "кількість": 0}

                    reservation_updates.append({"product_id": product.id, "quantity": item.quantity})

                    if item.quantity <= available:
                        item_for_excel["кількість"] = item.quantity
                        in_stock_items.append(item_for_excel)
                    else:
                        if available > 0:
                            item_for_excel["кількість"] = available
                            in_stock_items.append(item_for_excel)
                        surplus_items.append({
                            "артикул": product.артикул,
                            "кількість": item.quantity - available
                        })

                if not in_stock_items and not surplus_items:
                    raise ValueError("Не вдалося обробити жодного товару зі списку.")

                if reservation_updates:
                    await orm_update_reserved_quantity(session, reservation_updates)

                file_path = await _save_list_to_excel(in_stock_items, user_id)

                if file_path and in_stock_items:
                    db_items = [{"article_name": p.product.назва, "quantity": p.quantity} for p in temp_list]
                    await orm_add_saved_list(session, user_id, os.path.basename(file_path), file_path, db_items)

                await orm_clear_temp_list(user_id)
            
            # --- ЗМІНА: Блок надсилання файлів та меню ---
            await callback.message.delete() # Видаляємо повідомлення "Зберігаю..."

            if 'file_path' in locals() and file_path and in_stock_items:
                await bot.send_document(user_id, FSInputFile(file_path), caption=LEXICON.MAIN_LIST_SAVED)

            if surplus_items:
                surplus_path = await _save_list_to_excel(surplus_items, user_id, "лишки_")
                if surplus_path:
                    await bot.send_document(user_id, FSInputFile(surplus_path), caption=LEXICON.SURPLUS_LIST_CAPTION)
                    os.remove(surplus_path)

            await callback.answer(LEXICON.PROCESSING_COMPLETE, show_alert=True)
            
            # Надсилаємо головне меню після всіх дій
            user = callback.from_user
            kb = get_admin_main_kb() if user.id in ADMIN_IDS else get_user_main_kb()
            text = LEXICON.CMD_START_ADMIN if user.id in ADMIN_IDS else LEXICON.CMD_START_USER
            await bot.send_message(user_id, text, reply_markup=kb)
            # --- КІНЕЦЬ ЗМІНИ ---

    except (SQLAlchemyError, ValueError) as e:
        logger.error("Помилка транзакції при збереженні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.TRANSACTION_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при збереженні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)