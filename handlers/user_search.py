from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.orm import orm_find_products, orm_get_product_by_id
from keyboards.inline import get_search_results_kb, get_add_to_list_kb

router = Router()

# Додаємо фільтр, щоб цей обробник не реагував на текст кнопок
@router.message(F.text.as_("text"))
async def search_handler(message: Message, text: str):
    """Обробляє текстові повідомлення як пошукові запити."""
    # Ігноруємо команди та занадто короткі запити
    if text.startswith('/') or len(text) < 4:
        return
    
    # Перевіряємо, чи текст не є однією з наших команд-кнопок
    known_commands = ["Новий список", "Мій список", "🗂️ Архів списків", "👑 Адмін-панель"]
    if text in known_commands:
        return

    products = await orm_find_products(text)
    
    if not products:
        await message.answer("На жаль, за вашим запитом нічого не знайдено.")
        return
    
    if len(products) == 1:
        product = products[0]
        await show_product_card(message, product)
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
        # Видаляємо стару клавіатуру, щоб уникнути безладу
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_product_card(callback.message, product)
    
    await callback.answer()

async def show_product_card(message: Message, product):
    """Формує та відправляє картку товару."""
    card_text = (
        f"✅ *Знайдено товар*\n\n"
        f"📝 *Назва:* {product.назва}\n"
        f"🏢 *Відділ:* {product.відділ}\n"
        f"📂 *Група:* {product.група}\n"
        f"📦 *Кількість на складі:* {product.кількість}\n"
        f"🛒 *Відкладено:* {product.відкладено}"
    )
    await message.answer(
        card_text,
        reply_markup=get_add_to_list_kb(product.id)
    )