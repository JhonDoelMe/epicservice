import os
import pandas as pd
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from database.orm import (
    orm_get_product_by_id, orm_update_reserved_quantity, orm_add_saved_list,
    orm_clear_temp_list, orm_add_item_to_temp_list, orm_get_temp_list, orm_get_temp_list_department
)
from config import ARCHIVES_PATH

router = Router()

class ListStates(StatesGroup):
    waiting_for_quantity = State()

@router.message(F.text == "Новий список")
async def new_list_handler(message: Message):
    await orm_clear_temp_list(message.from_user.id)
    await message.answer("Створено новий порожній список. Тепер шукайте товари та додавайте їх.")

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
    
    save_button = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💾 Зберегти та відкласти", callback_data="save_list")]])
    await message.answer("\n".join(response_lines), reply_markup=save_button)

@router.callback_query(F.data.startswith("add_to_list:"))
async def add_to_list_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    product_id = int(callback.data.split(":", 1)[1])
    product = await orm_get_product_by_id(product_id)
    if not product:
        await callback.answer("Помилка: товар не знайдено.", show_alert=True)
        return
    
    allowed_department = await orm_get_temp_list_department(user_id)
    if allowed_department is not None and product.відділ != allowed_department:
        await callback.answer(f"Заборонено! Усі товари повинні бути з відділу {allowed_department}.", show_alert=True)
        return
    
    await state.update_data(product_id=product_id, product_name=product.назва, article=product.артикул)
    await state.set_state(ListStates.waiting_for_quantity)
    await callback.message.answer(f"Введіть кількість для товару:\n`{product.назва}`")
    await callback.answer()

@router.message(ListStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    quantity = int(message.text)
    data = await state.get_data()
    await orm_add_item_to_temp_list(user_id=message.from_user.id, product_id=data.get("product_id"), quantity=quantity)
    await message.answer(f"Товар `{data.get('article')}` у кількості *{quantity}* додано до списку.")
    await state.clear()

@router.callback_query(F.data == "save_list")
async def save_list_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    temp_list = await orm_get_temp_list(user_id)
    if not temp_list:
        await callback.answer("Список порожній.", show_alert=True)
        return

    archive_dir = os.path.join(ARCHIVES_PATH, f"user_{user_id}")
    os.makedirs(archive_dir, exist_ok=True)
    
    first_article_name = temp_list[0].product.артикул
    file_name = f"{first_article_name}.xlsx"
    file_path = os.path.join(archive_dir, file_name)
    
    excel_data = [{'артикул': item.product.артикул, 'кількість': item.quantity} for item in temp_list]
    df_list = pd.DataFrame(excel_data)

    try:
        df_list.to_excel(file_path, index=False, header=False)
        items_for_db = [{'article_name': item.product.назва, 'quantity': item.quantity} for item in temp_list]
        await orm_add_saved_list(user_id, file_name, file_path, items_for_db)
        
        items_to_reserve = [{'product_id': item.product_id, 'quantity': item.quantity} for item in temp_list]
        await orm_update_reserved_quantity(items_to_reserve)
        
        await orm_clear_temp_list(user_id)
        
        document = FSInputFile(file_path)
        await callback.message.answer_document(document, caption="Ваш список збережено, товари відкладено, а файл додано до архіву.")
        
    except Exception as e:
        await callback.message.answer(f"Сталася помилка: {e}")
    finally:
        await callback.answer("Список збережено!")