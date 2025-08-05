import os
import pandas as pd
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from database.orm import orm_get_product_by_id, orm_update_reserved_quantity, orm_add_saved_list

router = Router()
user_lists = {}

class ListStates(StatesGroup):
    waiting_for_quantity = State()

# ... (код обробників new_list, my_list, add_to_list, process_quantity залишається без змін) ...
@router.message(F.text == "Новий список")
async def new_list_handler(message: Message):
    user_id = message.from_user.id
    user_lists[user_id] = {"list": [], "first_article_name": None, "allowed_department": None}
    await message.answer("Створено новий порожній список.")

@router.message(F.text == "Мій список")
async def my_list_handler(message: Message):
    user_id = message.from_user.id
    if user_id not in user_lists or not user_lists[user_id]["list"]:
        await message.answer("Ваш список порожній.")
        return
    list_items = user_lists[user_id]["list"]
    department_id = user_lists[user_id]["allowed_department"]
    response_lines = [f"*Ваш поточний список (Відділ: {department_id}):*\n"]
    for i, item in enumerate(list_items, 1):
        article = item['article_name'].split(' - ')[0]
        response_lines.append(f"{i}. `{article}` ({item['article_name'][len(article)+3:]})\n   Кількість: *{item['quantity']}*")
    response_text = "\n".join(response_lines)
    save_button = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💾 Зберегти та відкласти", callback_data="save_list")]])
    await message.answer(response_text, reply_markup=save_button)

@router.callback_query(F.data.startswith("add_to_list:"))
async def add_to_list_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    product_id = int(callback.data.split(":", 1)[1])
    product = await orm_get_product_by_id(product_id)
    if not product:
        await callback.answer("Помилка: товар не знайдено.", show_alert=True)
        return
    if user_id not in user_lists:
        user_lists[user_id] = {"list": [], "first_article_name": None, "allowed_department": None}
    allowed_department = user_lists[user_id].get("allowed_department")
    if allowed_department is not None and product.відділ != allowed_department:
        await callback.answer(f"Заборонено! Товари мають бути з відділу {allowed_department}.", show_alert=True)
        return
    await state.update_data(product_id=product_id, product_name=product.назва)
    await state.set_state(ListStates.waiting_for_quantity)
    await callback.message.answer(f"Введіть кількість для товару:\n`{product.назва}`")
    await callback.answer()

@router.message(ListStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    user_id = message.from_user.id
    quantity = int(message.text)
    data = await state.get_data()
    product_id, product_name = data.get("product_id"), data.get("product_name")
    if not user_lists[user_id]["list"]:
        product = await orm_get_product_by_id(product_id)
        if product:
            user_lists[user_id]["allowed_department"] = product.відділ
            user_lists[user_id]["first_article_name"] = product.назва.split(' - ')[0]
    user_lists[user_id]["list"].append({"product_id": product_id, "article_name": product_name, "quantity": quantity})
    article_display = product_name.split(' - ')[0]
    await message.answer(f"Товар `{article_display}` у кількості *{quantity}* додано.")
    await state.clear()

# --- ОНОВЛЕНА ЛОГІКА ЗБЕРЕЖЕННЯ ---
@router.callback_query(F.data == "save_list")
async def save_list_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_lists or not user_lists[user_id]["list"]:
        await callback.answer("Список порожній.", show_alert=True)
        return

    user_data = user_lists[user_id]
    
    # Створюємо директорію для архівів, якщо її немає
    archive_dir = f"archives/user_{user_id}"
    os.makedirs(archive_dir, exist_ok=True)
    
    file_name = f"{str(user_data['first_article_name'])}.xlsx"
    file_path = os.path.join(archive_dir, file_name)
    
    excel_data = [{'артикул': item['article_name'].split(' - ')[0], 'кількість': item['quantity']} for item in user_data["list"]]
    df_list = pd.DataFrame(excel_data)

    try:
        df_list.to_excel(file_path, index=False, header=False)
        
        # Записуємо інформацію про збережений файл в БД
        await orm_add_saved_list(user_id, file_name, file_path, user_data['list'])
        
        # Оновлюємо поле 'відкладено' в БД
        items_to_reserve = [{'product_id': item['product_id'], 'quantity': item['quantity']} for item in user_data['list']]
        await orm_update_reserved_quantity(items_to_reserve)
        
        # Відправляємо файл користувачу
        document = FSInputFile(file_path)
        await callback.message.answer_document(document, caption="Ваш список збережено, товари відкладено, а файл додано до архіву.")
        
        del user_lists[user_id]
        
    except Exception as e:
        await callback.message.answer(f"Сталася помилка: {e}")
    finally:
        await callback.answer("Список збережено!")