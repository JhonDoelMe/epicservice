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

logger = logging.getLogger(__name__)

router = Router()

class ListStates(StatesGroup):
    """Стани для FSM, пов'язані з роботою зі списками."""
    waiting_for_quantity = State()
    confirm_new_list = State()

async def _save_list_to_excel(
    items: List[Dict[str, Any]],
    user_id: int,
    prefix: str = ""
) -> Optional[str]:
    """
    Зберігає список товарів у файл Excel.

    Args:
        items: Список словників з даними товарів ('артикул', 'кількість').
        user_id: ID користувача для створення унікальної папки.
        prefix: Префікс для назви файлу (напр., 'лишки_').

    Returns:
        Шлях до створеного файлу або None у разі помилки.
    """
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
    """Запитує підтвердження на створення нового списку, що видалить поточний."""
    await message.answer(
        LEXICON.NEW_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("confirm_new_list", "cancel_new_list"),
    )
    await state.set_state(ListStates.confirm_new_list)

@router.callback_query(ListStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
    """Обробляє підтвердження створення нового списку: очищує старий тимчасовий список."""
    user_id = callback.from_user.id
    await state.clear()
    try:
        await orm_clear_temp_list(user_id)
        logger.info("Користувач %s створив новий список (очищено тимчасовий список).", user_id)
        await callback.message.edit_text(LEXICON.NEW_LIST_CONFIRMED)
    except SQLAlchemyError as e:
        logger.error("Помилка очищення списку для користувача %s: %s", user_id, e)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await callback.answer()

@router.callback_query(ListStates.confirm_new_list, F.data == "cancel_new_list")
async def new_list_canceled(callback: CallbackQuery, state: FSMContext):
    """Обробляє скасування створення нового списку."""
    await state.clear()
    await callback.message.edit_text(LEXICON.ACTION_CANCELED)
    await callback.answer()

@router.message(F.text == LEXICON.BUTTON_MY_LIST)
async def my_list_handler(message: Message):
    """Відображає поточний (тимчасовий) список товарів користувача."""
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
            # Видаляємо артикул з початку назви для кращого відображення
            name_without_article = item.product.назва.replace(f"{article} - ", "", 1)
            response_lines.append(
                LEXICON.MY_LIST_ITEM.format(
                    i=i,
                    article=article,
                    name=name_without_article,
                    quantity=item.quantity,
                )
            )

        save_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=LEXICON.SAVE_LIST_BUTTON, callback_data="save_list")]
        ])
        await message.answer("\n".join(response_lines), reply_markup=save_button)
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

            # Перевірка на відповідність відділу
            allowed_department = await orm_get_temp_list_department(user_id)
            if allowed_department is not None and product.відділ != allowed_department:
                await callback.answer(
                    LEXICON.DEPARTMENT_MISMATCH.format(department=allowed_department),
                    show_alert=True,
                )
                return

            await orm_add_item_to_temp_list(user_id, product_id, quantity)
            logger.info("Користувач %s додав товар ID %s (кількість: %s) до списку.", user_id, product_id, quantity)

            await callback.message.edit_text(
                callback.message.text + f"\n\n✅ *Додано {quantity} шт.*",
            )
            await callback.answer(f"Додано {product.артикул}")

    except (ValueError, IndexError) as e:
        logger.error("Помилка парсингу даних у add_all_callback: %s", callback.data, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    except Exception as e:
        logger.error("Неочікувана помилка додавання товару для %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.callback_query(F.data.startswith("add_custom:"))
async def add_custom_callback(callback: CallbackQuery, state: FSMContext):
    """Ініціює процес додавання товару з кастомною кількістю."""
    user_id = callback.from_user.id
    try:
        product_id = int(callback.data.split(":", 1)[1])

        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return

            # Перевірка на відповідність відділу
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
                LEXICON.ENTER_QUANTITY.format(product_name=product.назва),
                reply_markup=cancel_kb,
            )
            await state.set_state(ListStates.waiting_for_quantity)
            await callback.answer()

    except (ValueError, IndexError) as e:
        logger.error("Помилка парсингу даних у add_custom_callback: %s", callback.data, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)
    except Exception as e:
        logger.error("Неочікувана помилка ініціації додавання товару %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.message(ListStates.waiting_for_quantity, F.text == "❌ Скасувати")
async def cancel_quantity_input(message: Message, state: FSMContext):
    """Обробляє скасування введення кількості товару."""
    await state.clear()
    reply_kb = admin_main_kb if message.from_user.id in ADMIN_IDS else user_main_kb
    await message.answer(LEXICON.CANCEL_ACTION, reply_markup=reply_kb)

@router.message(ListStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    """Обробляє введену користувачем кількість товару."""
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
        logger.info("Користувач %s додав товар ID %s (кількість: %s) через введення.", user_id, product_id, quantity)

        await message.answer(
            LEXICON.ITEM_ADDED_TO_LIST.format(
                article=data.get("article"), quantity=quantity
            ),
            reply_markup=reply_kb,
        )
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число.", reply_markup=cancel_kb)
    except Exception as e:
        logger.error("Помилка обробки кількості для користувача %s: %s", user_id, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)
    finally:
        await state.clear()

@router.callback_query(F.data == "save_list")
async def save_list_callback(callback: CallbackQuery):
    """
    Ключова функція. Зберігає поточний список: перевіряє залишки, резервує товари,
    створює Excel-файли для наявних товарів та для лишків, зберігає запис в БД.
    Всі операції з БД відбуваються в одній атомарній транзакції.
    """
    user_id = callback.from_user.id
    logger.info("Користувач %s ініціював збереження списку.", user_id)
    
    await callback.message.edit_text(LEXICON.SAVING_LIST_PROCESS)

    try:
        async with async_session() as session:
            temp_list = await orm_get_temp_list(user_id)
            if not temp_list:
                await callback.message.edit_text(LEXICON.EMPTY_LIST)
                await callback.answer(show_alert=True)
                return

            in_stock_items, surplus_items, reservation_updates = [], [], []

            # Початок атомарної транзакції
            async with session.begin():
                for item in temp_list:
                    # Блокуємо рядок товару для безпечного оновлення
                    product = await orm_get_product_by_id(session, item.product_id, for_update=True)
                    if not product:
                        continue # Пропускаємо, якщо товар раптом видалили

                    try:
                        stock_qty = float(product.кількість)
                    except (ValueError, TypeError):
                        stock_qty = 0
                    
                    # Розраховуємо доступну кількість
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

                # Крок 1: Оновлюємо резерви в БД
                if reservation_updates:
                    await orm_update_reserved_quantity(session, reservation_updates)

                # Крок 2: Зберігаємо основний список в Excel
                file_path = await _save_list_to_excel(in_stock_items, user_id)

                # Крок 3: Створюємо запис про збережений список в БД
                if file_path and in_stock_items:
                    # Готуємо дані про товари для запису в БД
                    db_items = [{"article_name": f"{p.product.назва}", "quantity": p.quantity} for p in temp_list]
                    await orm_add_saved_list(user_id, os.path.basename(file_path), file_path, db_items, session)

                # Крок 4: Очищуємо тимчасовий список
                await orm_clear_temp_list(user_id)

            # Кінець атомарної транзакції. commit() викликається автоматично.

            # Відправляємо файли користувачу
            if file_path and in_stock_items:
                await callback.message.answer_document(FSInputFile(file_path), caption=LEXICON.MAIN_LIST_SAVED)

            if surplus_items:
                surplus_path = await _save_list_to_excel(surplus_items, user_id, "лишки_")
                if surplus_path:
                    await callback.message.answer_document(FSInputFile(surplus_path), caption=LEXICON.SURPLUS_LIST_CAPTION)
                    os.remove(surplus_path) # Файл з лишками є тимчасовим

            await callback.message.delete() # Видаляємо повідомлення "Перевіряю залишки..."
            await callback.answer(LEXICON.PROCESSING_COMPLETE, show_alert=True)

    except (SQLAlchemyError, ValueError) as e:
        logger.critical("Критична помилка збереження списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.TRANSACTION_ERROR)
    except Exception as e:
        logger.error("Неочікувана помилка при збереженні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.answer(LEXICON.UNEXPECTED_ERROR)