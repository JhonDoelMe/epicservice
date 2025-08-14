import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS, ARCHIVES_PATH
from database.engine import async_session
from database.orm import (orm_add_item_to_temp_list, orm_add_saved_list,
                          orm_clear_temp_list, orm_get_product_by_id,
                          orm_get_temp_list, orm_get_temp_list_department,
                          orm_update_reserved_quantity)
from keyboards.inline import get_confirmation_kb
from keyboards.reply import admin_main_kb, cancel_kb, user_main_kb
from lexicon.lexicon import LEXICON
from utils.markdown_corrector import escape_markdown

logger = logging.getLogger(__name__)

router = Router()

class ListStates(StatesGroup):
    waiting_for_quantity = State()
    confirm_new_list = State()

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

@router.message(F.text == LEXICON.BUTTON_NEW_LIST)
async def new_list_handler(message: Message, state: FSMContext):
    await message.answer(
        LEXICON.NEW_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("confirm_new_list", "cancel_new_list"),
    )
    await state.set_state(ListStates.confirm_new_list)

@router.callback_query(ListStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.clear()
    try:
        await orm_clear_temp_list(user_id)
        await callback.message.edit_text(LEXICON.NEW_LIST_CONFIRMED)
    except SQLAlchemyError as e:
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await callback.answer()

@router.callback_query(ListStates.confirm_new_list, F.data == "cancel_new_list")
async def new_list_canceled(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(LEXICON.ACTION_CANCELED)
    await callback.answer()

@router.message(F.text == LEXICON.BUTTON_MY_LIST)
async def my_list_handler(message: Message):
    """
    Відображає поточний список товарів у форматі "артикул - кількість"
    та має захист від занадто довгих повідомлень.
    """
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb

    try:
        temp_list = await orm_get_temp_list(user_id)
        if not temp_list:
            await message.answer(LEXICON.EMPTY_LIST, reply_markup=reply_kb)
            return

        department_id = temp_list[0].product.відділ
        
        # --- ФОРМАТУВАННЯ ТА ЗАХИСТ ВІД ДОВГИХ ПОВІДОМЛЕНЬ ---
        header = [f"*Ваш поточний список (Відділ: {department_id}):*"]
        
        # Формуємо список у форматі "артикул - кількість"
        list_items = [
            f"`{item.product.артикул}` - *{item.quantity}* шт." 
            for item in temp_list
        ]

        # Розділяємо повідомлення на частини, якщо потрібно
        max_length = 4096
        parts = []
        current_part = "\n".join(header)

        for line in list_items:
            if len(current_part) + len(line) + 1 > max_length:
                parts.append(current_part)
                current_part = line
            else:
                current_part += "\n" + line
        
        parts.append(current_part)

        # Відправляємо всі частини
        for i, part in enumerate(parts):
            # Кнопку збереження додаємо тільки до останньої частини
            if i == len(parts) - 1:
                save_button = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=LEXICON.SAVE_LIST_BUTTON, callback_data="save_list")]
                ])
                await message.answer(part, reply_markup=save_button)
            else:
                await message.answer(part)
        
        await message.answer(LEXICON.FORGET_NOT_TO_SAVE, reply_markup=reply_kb)

    except Exception as e:
        logger.error("Помилка отримання списку для користувача %s: %s", user_id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)


@router.callback_query(F.data.startswith("add_all:"))
async def add_all_callback(callback: CallbackQuery, state: FSMContext):
    """Додає всю доступну кількість товару до тимчасового списку."""
    user_id = callback.from_user.id
    try:
        _, product_id_str, quantity_str = callback.data.split(":")
        product_id = int(product_id_str)
        quantity = int(quantity_str)

        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return

            allowed_department = await orm_get_temp_list_department(user_id)
            if allowed_department is not None and product.відділ != allowed_department:
                await callback.answer(
                    LEXICON.DEPARTMENT_MISMATCH.format(department=allowed_department),
                    show_alert=True,
                )
                return

            await orm_add_item_to_temp_list(user_id, product_id, quantity)
            logger.info("Користувач %s додав товар ID %s (кількість: %s) до списку.", user_id, product_id, quantity)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"✅ *Додано {quantity} шт.*")
            await callback.answer()

    except (ValueError, IndexError) as e:
        logger.error("Помилка парсингу даних у add_all_callback: %s", callback.data, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    except Exception as e:
        logger.error("Неочікувана помилка додавання товару для %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.callback_query(F.data.startswith("add_custom:"))
async def add_custom_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    try:
        product_id = int(callback.data.split(":", 1)[1])

        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return

            allowed_department = await orm_get_temp_list_department(user_id)
            if allowed_department is not None and product.відділ != allowed_department:
                await callback.answer(
                    LEXICON.DEPARTMENT_MISMATCH.format(department=allowed_department),
                    show_alert=True,
                )
                return

            await state.update_data(product_id=product.id, article=product.артикул, product_name=product.назва)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                LEXICON.ENTER_QUANTITY.format(product_name=escape_markdown(product.назва)),
                reply_markup=cancel_kb,
            )
            await state.set_state(ListStates.waiting_for_quantity)
            await callback.answer()

    except (ValueError, IndexError):
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    except Exception as e:
        logger.error("Неочікувана помилка ініціації додавання товару %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.message(ListStates.waiting_for_quantity, F.text == "❌ Скасувати")
async def cancel_quantity_input(message: Message, state: FSMContext):
    await state.clear()
    reply_kb = admin_main_kb if message.from_user.id in ADMIN_IDS else user_main_kb
    await message.answer(LEXICON.CANCEL_ACTION, reply_markup=reply_kb)

@router.message(ListStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb
    
    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("Кількість має бути більше нуля.", reply_markup=cancel_kb)
            return

        data = await state.get_data()
        product_id = data.get("product_id")
        
        await orm_add_item_to_temp_list(user_id, product_id, quantity)

        await message.answer(
            LEXICON.ITEM_ADDED_TO_LIST.format(
                article=data.get("article"), quantity=quantity
            ),
            reply_markup=reply_kb,
        )
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число.", reply_markup=cancel_kb)
    except Exception as e:
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)
    finally:
        await state.clear()

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
                    
                    if item.quantity <= available:
                        item_for_excel["кількість"] = item.quantity
                        in_stock_items.append(item_for_excel)
                        reservation_updates.append({"product_id": product.id, "quantity": item.quantity})
                    else:
                        if available > 0:
                            item_for_excel["кількість"] = available
                            in_stock_items.append(item_for_excel)
                            reservation_updates.append({"product_id": product.id, "quantity": available})
                        
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
                    db_items = [{"article_name": f"{p.product.назва}", "quantity": p.quantity} for p in temp_list]
                    await orm_add_saved_list(user_id, os.path.basename(file_path), file_path, db_items, session)

                await orm_clear_temp_list(user_id)

            if file_path and in_stock_items:
                await callback.message.answer_document(FSInputFile(file_path), caption=LEXICON.MAIN_LIST_SAVED)

            if surplus_items:
                surplus_path = await _save_list_to_excel(surplus_items, user_id, "лишки_")
                if surplus_path:
                    await callback.message.answer_document(FSInputFile(surplus_path), caption=LEXICON.SURPLUS_LIST_CAPTION)
                    os.remove(surplus_path)

            await callback.message.delete()
            await callback.answer(LEXICON.PROCESSING_COMPLETE, show_alert=True)

    except (SQLAlchemyError, ValueError) as e:
        await callback.message.answer(LEXICON.TRANSACTION_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при збереженні списку для %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR)