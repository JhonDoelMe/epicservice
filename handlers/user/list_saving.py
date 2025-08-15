# epicservice/handlers/user/list_saving.py

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.exc import SQLAlchemyError

from config import ARCHIVES_PATH
from database.engine import async_session
from database.orm import (orm_add_saved_list, orm_clear_temp_list,
                          orm_get_product_by_id, orm_get_temp_list,
                          orm_update_reserved_quantity)
from lexicon.lexicon import LEXICON

# ... (решта файлу без змін до функції save_list_callback) ...
logger = logging.getLogger(__name__)
router = Router()

async def _save_list_to_excel(
    items: List[Dict[str, Any]],
    user_id: int,
    prefix: str = ""
) -> Optional[str]:
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
async def save_list_callback(callback: CallbackQuery):
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

                    # --- ВИПРАВЛЕНО: Логіка резервування ---
                    # Незалежно від наявності, ми резервуємо повну кількість, яку хоче користувач
                    reservation_updates.append({"product_id": product.id, "quantity": item.quantity})

                    if item.quantity <= available:
                        # Якщо товару вистачає, він йде в основний файл
                        item_for_excel["кількість"] = item.quantity
                        in_stock_items.append(item_for_excel)
                    else:
                        # Якщо товару не вистачає
                        if available > 0:
                            # Частина, що є, йде в основний файл
                            item_for_excel["кількість"] = available
                            in_stock_items.append(item_for_excel)
                        # Різниця йде у файл лишків
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

            if 'file_path' in locals() and file_path and in_stock_items:
                await callback.message.answer_document(FSInputFile(file_path), caption=LEXICON.MAIN_LIST_SAVED)

            if surplus_items:
                surplus_path = await _save_list_to_excel(surplus_items, user_id, "лишки_")
                if surplus_path:
                    await callback.message.answer_document(FSInputFile(surplus_path), caption=LEXICON.SURPLUS_LIST_CAPTION)
                    os.remove(surplus_path)

            await callback.message.delete()
            await callback.answer(LEXICON.PROCESSING_COMPLETE, show_alert=True)

    except (SQLAlchemyError, ValueError) as e:
        logger.error("Помилка транзакції при збереженні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.TRANSACTION_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при збереженні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)