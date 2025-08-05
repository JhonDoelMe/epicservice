from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.orm import orm_find_products, orm_get_product_by_id
from keyboards.inline import get_search_results_kb, get_add_to_list_kb

router = Router()

def format_quantity(quantity_str: str):
    """
    Форматує кількість:
    - Якщо число ціле (наприклад, "22.0" або "22"), повертає "22".
    - Якщо число дробове (наприклад, "0.156"), повертає "0.156".
    """
    try:
        quantity_float = float(quantity_str)
        if quantity_float.is_integer():
            return int(quantity_float)
        else:
            return quantity_float
    except (ValueError, TypeError):
        # Якщо це не число, повертаємо як є
        return quantity_str

@router.message(F.text.as_("text"))
async def search_handler(message: Message, text: str):
    """Обробляє текстові повідомлення як пошукові запити."""
    known_commands = ["Новий список", "Мій список", "🗂️ Архів списків", "👑 Адмін-панель"]
    if text.startswith('/') or text in known_commands:
        return

    if len(text) < 5:
        await message.answer("⚠️ Будь ласка, введіть для пошуку не менше 5 символів.")
        return

    products = await orm_find_products(text)
    
    if not products:
        await message.answer("На жаль, за вашим запитом нічого не знайдено.")
        return
    
    if len(products) == 1:
        await show_product_card(message, products[0])
    else:
        await message.answer(
            "Знайдено кілька варіантів. Будь ласка, оберіть потрібний:",
            reply_markup=get_search_results_kb(products)
        )

@router.callback_query(F.data.startswith("product:"))
async def show_product_from_button(callback: CallbackQuery):
    """Показує картку товару після натискання на кнопку (використовує ID)."""
    product_id = int(callback.data.split(":", 1)[1])
    product = await orm_get_product_by_id(product_id)
    
    if product:
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_product_card(callback.message, product)
    
    await callback.answer()

async def show_product_card(message: Message, product):
    """Формує та відправляє картку товару."""
    try:
        # --- НОВА ЛОГІКА: Обчислюємо доступний залишок ---
        stock_quantity = float(product.кількість)
        reserved_quantity = product.відкладено or 0
        available_quantity = stock_quantity - reserved_quantity
        
        # Форматуємо для красивого виводу
        display_available = format_quantity(str(available_quantity))
    except (ValueError, TypeError):
        display_available = product.кількість # Якщо не можемо порахувати, показуємо як є

    card_text = (
        f"✅ *Знайдено товар*\n\n"
        f"📝 *Назва:* {product.назва}\n"
        f"🏢 *Відділ:* {product.відділ}\n"
        f"📂 *Група:* {product.група}\n"
        f"📦 *Доступно для збирання:* {display_available}\n" # <-- ЗМІНЕНО ТУТ
        f"🛒 *Вже зібрано:* {product.відкладено}" # <-- ЗМІНЕНО ТУТ
    )
    await message.answer(
        card_text,
        reply_markup=get_add_to_list_kb(product.id)
    )