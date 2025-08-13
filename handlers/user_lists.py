import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

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

# Налаштування логування
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
    """
    Зберігає список товарів у Excel файл
    Повертає шлях до файлу або None у разі помилки
    """
    try:
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
        first_article = items[0]['артикул']
        file_name = f"{prefix}{first_article}_{timestamp}.xlsx"
        
        archive_dir = os.path.join(ARCHIVES_PATH, f"user_{user_id}")
        os.makedirs(archive_dir, exist_ok=True)
        file_path = os.path.join(archive_dir, file_name)
        
        df = pd.DataFrame(items)
        df.to_excel(file_path, index=False, header=False)
        
        logger.info("Файл успішно збережено: %s", file_path)
        return file_path
    except Exception as e:
        logger.error("Помилка збереження Excel файлу: %s", e, exc_info=True)
        return None

@router.message(F.text == "Новий список")
async def new_list_handler(message: Message, state: FSMContext):
    """Обробник створення нового списку"""
    await message.answer(
        LEXICON.NEW_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("confirm_new_list", "cancel_new_list"),
    )
    await state.set_state(ListStates.confirm_new_list)

@router.callback_query(ListStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
    """Підтвердження створення нового списку"""
    user_id = callback.from_user.id
    try:
        await orm_clear_temp_list(user_id)
        logger.info("Користувач %s створив новий список (очищено тимчасовий список)", user_id)
        await callback.message.edit_text(LEXICON.NEW_LIST_CONFIRMED)
    except SQLAlchemyError as e:
        logger.error("Помилка очищення списку для користувача %s: %s", user_id, e)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await state.clear()
        await callback.answer()

@router.callback_query(ListStates.confirm_new_list, F.data == "cancel_new_list")
async def new_list_canceled(callback: CallbackQuery, state: FSMContext):
    """Скасування створення нового списку"""
    await callback.message.edit_text(LEXICON.ACTION_CANCELED)
    await state.clear()
    await callback.answer()

@router.message(F.text == "Мій список")
async def my_list_handler(message: Message):
    """Показ поточного списку товарів користувача"""
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb

    try:
        temp_list = await orm_get_temp_list(user_id)
        if not temp_list:
            await message.answer(LEXICON.EMPTY_LIST, reply_markup=reply_kb)
            return

        department_id = temp_list[0].product.відділ
        response_lines = [LEXICON.MY_LIST_TITLE.format(department=department_id)]

        for i, item in enumerate(temp_list, 1):
            article = item.product.артикул
            full_name = item.product.назва
            response_lines.append(
                LEXICON.MY_LIST_ITEM.format(
                    i=i,
                    article=article,
                    name=full_name[len(article) + 3 :],
                    quantity=item.quantity,
                )
            )

        save_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=LEXICON.SAVE_LIST_BUTTON, callback_data="save_list"
                    )
                ]
            ]
        )
        await message.answer("\n".join(response_lines), reply_markup=save_button)
        await message.answer(LEXICON.FORGET_NOT_TO_SAVE, reply_markup=reply_kb)
    except Exception as e:
        logger.error("Помилка отримання списку для користувача %s: %s", user_id, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)

@router.callback_query(F.data.startswith("add_all:"))
async def add_all_callback(callback: CallbackQuery):
    """Додавання всієї доступної кількості товару"""
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

            await orm_add_item_to_temp_list(
                user_id=user_id, product_id=product_id, quantity=quantity
            )
            logger.info(
                "Користувач %s додав товар ID %s (кількість: %s) до списку",
                user_id, product_id, quantity
            )

            await callback.message.answer(
                LEXICON.ITEM_ADDED_TO_LIST.format(
                    article=product.артикул, quantity=quantity
                )
            )
    except ValueError as e:
        logger.error("Помилка парсингу даних у add_all: %s", e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    except Exception as e:
        logger.error("Помилка додавання товару для користувача %s: %s", user_id, e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("add_custom:"))
async def add_custom_callback(callback: CallbackQuery, state: FSMContext):
    """Додавання товару з вибором кількості"""
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

            await state.update_data(product_id=product_id, article=product.артикул)
            await callback.message.answer(
                LEXICON.ENTER_QUANTITY.format(product_name=product.назва),
                reply_markup=cancel_kb,
            )
            await state.set_state(ListStates.waiting_for_quantity)
    except Exception as e:
        logger.error("Помилка додавання товару для користувача %s: %s", user_id, e)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    finally:
        await callback.answer()

@router.message(ListStates.waiting_for_quantity, F.text == "❌ Скасувати")
async def cancel_quantity_input(message: Message, state: FSMContext):
    """Скасування введення кількості"""
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb
    await state.clear()
    await message.answer(LEXICON.CANCEL_ACTION, reply_markup=reply_kb)

@router.message(ListStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    """Обробка введеної кількості товару"""
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb
    
    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("Кількість має бути більше 0", reply_markup=reply_kb)
            return

        data = await state.get_data()
        product_id = data.get("product_id")
        
        await orm_add_item_to_temp_list(
            user_id=user_id, product_id=product_id, quantity=quantity
        )
        logger.info(
            "Користувач %s додав товар ID %s (кількість: %s) через власне введення",
            user_id, product_id, quantity
        )

        await message.answer(
            LEXICON.ITEM_ADDED_TO_LIST.format(
                article=data.get("article"), quantity=quantity
            ),
            reply_markup=reply_kb,
        )
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число", reply_markup=reply_kb)
    except Exception as e:
        logger.error("Помилка обробки кількості для користувача %s: %s", user_id, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)
    finally:
        await state.clear()

@router.callback_query(F.data == "save_list")
async def save_list_callback(callback: CallbackQuery):
    """Збереження списку товарів"""
    user_id = callback.from_user.id
    logger.info("Користувач %s ініціював збереження списку", user_id)
    
    try:
        async with async_session() as session:
            temp_list = await orm_get_temp_list(user_id)
            if not temp_list:
                await callback.answer(LEXICON.EMPTY_LIST, show_alert=True)
                return

            await callback.message.edit_text(LEXICON.SAVING_LIST_PROCESS)
            
            in_stock_list = []
            surplus_list = []
            items_to_reserve = []
            
            for item in temp_list:
                async with session.begin():
                    product = await orm_get_product_by_id(
                        session, item.product_id, for_update=True
                    )
                    if not product:
                        continue
                        
                    try:
                        stock_qty = float(product.кількість)
                    except (ValueError, TypeError):
                        stock_qty = 0
                        
                    available = stock_qty - (product.відкладено or 0)
                    
                    if item.quantity <= available:
                        in_stock_list.append({
                            "артикул": product.артикул,
                            "кількість": item.quantity
                        })
                        items_to_reserve.append({
                            "product_id": product.id,
                            "quantity": item.quantity
                        })
                    else:
                        if available > 0:
                            in_stock_list.append({
                                "артикул": product.артикул,
                                "кількість": available
                            })
                            items_to_reserve.append({
                                "product_id": product.id,
                                "quantity": available
                            })
                        surplus_list.append({
                            "артикул": product.артикул,
                            "кількість": item.quantity - available
                        })
            
            if items_to_reserve:
                await orm_update_reserved_quantity(session, items_to_reserve)
                
            # Збереження основного списку
            if in_stock_list:
                file_path = await _save_list_to_excel(in_stock_list, user_id)
                if file_path:
                    items_for_db = [{
                        "article_name": f"{item.product.артикул} {item.product.назва}",
                        "quantity": item.quantity
                    } for item in temp_list]
                    
                    await orm_add_saved_list(
                        user_id, 
                        os.path.basename(file_path), 
                        file_path, 
                        items_for_db, 
                        session
                    )
                    await session.commit()
                    
                    document = FSInputFile(file_path)
                    await callback.message.answer_document(
                        document, 
                        caption=LEXICON.MAIN_LIST_SAVED
                    )
                    logger.info("Користувач %s успішно зберіг основний список", user_id)

            # Збереження списку лишків
            if surplus_list:
                surplus_path = await _save_list_to_excel(surplus_list, user_id, "лишки_")
                if surplus_path:
                    document = FSInputFile(surplus_path)
                    await callback.message.answer_document(
                        document,
                        caption=LEXICON.SURPLUS_LIST_CAPTION
                    )
                    logger.info("Користувач %s згенерував список лишків", user_id)
                    os.remove(surplus_path)
            
            # Очистка тимчасового списку
            await orm_clear_temp_list(user_id)
            await callback.answer(LEXICON.PROCESSING_COMPLETE, show_alert=True)
            
    except SQLAlchemyError as e:
        logger.error("Помилка БД при збереженні списку для %s: %s", user_id, e)
        await callback.message.answer(LEXICON.TRANSACTION_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при збереженні списку для %s: %s", user_id, e)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)