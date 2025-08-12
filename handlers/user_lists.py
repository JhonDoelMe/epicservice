import logging
import os

import pandas as pd
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from config import ARCHIVES_PATH
from database.engine import async_session
from database.orm import (orm_add_item_to_temp_list, orm_add_saved_list,
                          orm_clear_temp_list, orm_get_product_by_id,
                          orm_get_temp_list, orm_get_temp_list_department,
                          orm_update_reserved_quantity)
from keyboards.inline import get_confirmation_kb
from keyboards.reply import cancel_kb, user_main_kb

router = Router()

class ListStates(StatesGroup):
    waiting_for_quantity = State()
    confirm_new_list = State()

@router.message(F.text == "Новий список")
async def new_list_handler(message: Message, state: FSMContext):
    await message.answer(
        "⚠️ Ви впевнені, що хочете створити новий список?\n"
        "**Весь поточний незбережений список буде видалено!**",
        reply_markup=get_confirmation_kb("confirm_new_list", "cancel_new_list")
    )
    await state.set_state(ListStates.confirm_new_list)

@router.callback_query(ListStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await orm_clear_temp_list(user_id)
    logging.info(f"User {user_id} created a new list (cleared temp list).")
    await callback.message.edit_text("✅ Створено новий порожній список. Тепер шукайте товари та додавайте їх.")
    await state.clear()
    await callback.answer()

@router.callback_query(ListStates.confirm_new_list, F.data == "cancel_new_list")
async def new_list_canceled(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Дію скасовано. Ваш поточний список залишається без змін.")
    await state.clear()
    await callback.answer()

@router.message(F.text == "Мій список")
async def my_list_handler(message: Message):
    user_id = message.from_user.id
    temp_list = await orm_get_temp_list(user_id)
    if not temp_list:
        await message.answer("Ваш список порожній.")
        return

    department_id = temp_list[0].product.відділ
    response_lines = [f"*Ваш поточний список (Відділ: {department_id}):*\n"]
    
    for i, item in enumerate(temp_list, 1):
        article = item.product.артикул
        full_name = item.product.назва
        response_lines.append(f"{i}. `{article}` ({full_name[len(article)+3:]})\n   Кількість: *{item.quantity}*")
    
    save_button = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💾 Зберегти та відкласти", callback_data="save_list")]]
    )
    await message.answer("\n".join(response_lines), reply_markup=save_button)

@router.callback_query(F.data.startswith("add_all:"))
async def add_all_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    product_id = int(parts[1])
    quantity = int(parts[2])

    async with async_session() as session:
        product = await orm_get_product_by_id(session, product_id)
        if not product:
            await callback.answer("Помилка: товар не знайдено.", show_alert=True)
            return

        allowed_department = await orm_get_temp_list_department(user_id)
        if allowed_department is not None and product.відділ != allowed_department:
            await callback.answer(f"Заборонено! Усі товари повинні бути з відділу {allowed_department}.", show_alert=True)
            return

        await orm_add_item_to_temp_list(user_id=user_id, product_id=product_id, quantity=quantity)
        logging.info(f"User {user_id} added product ID {product_id} (quantity: {quantity}) to temp list.")
    
        article_display = product.артикул
        await callback.message.answer(f"Товар `{article_display}` у кількості *{quantity}* додано до списку.")
    await callback.answer()

@router.callback_query(F.data.startswith("add_custom:"))
async def add_custom_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    product_id = int(callback.data.split(":", 1)[1])
    
    async with async_session() as session:
        product = await orm_get_product_by_id(session, product_id)
        if not product:
            await callback.answer("Помилка: товар не знайдено.", show_alert=True)
            return
        
        allowed_department = await orm_get_temp_list_department(user_id)
        if allowed_department is not None and product.відділ != allowed_department:
            await callback.answer(f"Заборонено! Усі товари повинні бути з відділу {allowed_department}.", show_alert=True)
            return
        
        await state.update_data(product_id=product_id, article=product.артикул)
        await callback.message.answer(f"Введіть кількість для товару:\n`{product.назва}`", reply_markup=cancel_kb)
        await state.set_state(ListStates.waiting_for_quantity)
    await callback.answer()

@router.message(ListStates.waiting_for_quantity, F.text == "❌ Скасувати")
async def cancel_quantity_input(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Дію скасовано.", reply_markup=user_main_kb)

@router.message(ListStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    quantity = int(message.text)
    user_id = message.from_user.id
    data = await state.get_data()
    product_id = data.get("product_id")
    await orm_add_item_to_temp_list(user_id=user_id, product_id=product_id, quantity=quantity)
    logging.info(f"User {user_id} added product ID {product_id} (quantity: {quantity}) via custom input.")
    await message.answer(f"Товар `{data.get('article')}` у кількості *{quantity}* додано до списку.", reply_markup=user_main_kb)
    await state.clear()

@router.callback_query(F.data == "save_list")
async def save_list_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    logging.info(f"User {user_id} initiated list saving.")
    temp_list = await orm_get_temp_list(user_id)
    if not temp_list:
        await callback.answer("Список порожній.", show_alert=True)
        return
    
    await callback.message.edit_text("Перевіряю залишки та формую списки...")
    in_stock_list, surplus_list, items_to_reserve = [], [], []

    try:
        async with async_session() as session:
            async with session.begin():
                for item in temp_list:
                    product = await orm_get_product_by_id(session, item.product_id, for_update=True)
                    if not product: continue
                    try:
                        stock_quantity = int(float(product.кількість))
                    except (ValueError, TypeError):
                        stock_quantity = 0
                    available_stock = stock_quantity - (product.відкладено or 0)
                    if item.quantity <= available_stock:
                        in_stock_list.append(item)
                        items_to_reserve.append({'product_id': item.product.id, 'quantity': item.quantity})
                    else:
                        if available_stock > 0:
                            in_stock_list.append(type('obj', (object,), {'product': item.product, 'quantity': available_stock})())
                            items_to_reserve.append({'product_id': item.product.id, 'quantity': available_stock})
                        surplus_list.append(type('obj', (object,), {'product': item.product, 'quantity': item.quantity - available_stock})())
                if items_to_reserve:
                    await orm_update_reserved_quantity(session, items_to_reserve)
    except Exception as e:
        logging.error(f"Transaction error for user {user_id} during list saving: {e}")
        await callback.message.answer(f"Сталася критична помилка під час перевірки залишків. Спробуйте знову.")
        return
    
    if in_stock_list:
        first_article_name = in_stock_list[0].product.артикул
        file_name = f"{first_article_name}.xlsx"
        archive_dir = os.path.join(ARCHIVES_PATH, f"user_{user_id}")
        os.makedirs(archive_dir, exist_ok=True)
        file_path = os.path.join(archive_dir, file_name)
        excel_data = [{'артикул': item.product.артикул, 'кількість': item.quantity} for item in in_stock_list]
        df_list = pd.DataFrame(excel_data)
        try:
            df_list.to_excel(file_path, index=False, header=False)
            async with async_session() as session:
                items_for_db = [{'article_name': item.product.назва, 'quantity': item.quantity} for item in in_stock_list]
                await orm_add_saved_list(user_id, file_name, file_path, items_for_db, session)
                await session.commit()
            document = FSInputFile(file_path)
            await callback.message.answer_document(document, caption=f"✅ **Основний список** збережено.")
            logging.info(f"User {user_id} successfully saved main list to {file_path}.")
        except Exception as e:
            logging.error(f"Error saving main list for user {user_id}: {e}")
            await callback.message.answer(f"Сталася помилка при збереженні основного списку: {e}")

    if surplus_list:
        first_article_name = surplus_list[0].product.артикул
        file_name = f"{first_article_name}-лишки.xlsx"
        file_path = f"temp_{file_name}"
        excel_data = [{'артикул': item.product.артикул, 'кількість': item.quantity} for item in surplus_list]
        df_list = pd.DataFrame(excel_data)
        try:
            df_list.to_excel(file_path, index=False, header=False)
            document = FSInputFile(file_path)
            await callback.message.answer_document(document, caption="⚠️ **УВАГА!**\nЦе список товарів, яких **не вистачило на складі** (лишки).")
            logging.info(f"User {user_id} generated a surplus list.")
        except Exception as e:
            logging.error(f"Error saving surplus list for user {user_id}: {e}")
            await callback.message.answer(f"Сталася помилка при збереженні списку лишків: {e}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    await orm_clear_temp_list(user_id)
    await callback.answer("Обробку завершено!")