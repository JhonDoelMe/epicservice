from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.engine import async_session
from database.orm import orm_find_products, orm_get_product_by_id
from keyboards.inline import get_product_actions_kb, get_search_results_kb
from lexicon.lexicon import LEXICON

router = Router()


def format_quantity(quantity_str: str):
    """Форматує кількість, прибираючи .0 для цілих чисел."""
    try:
        quantity_float = float(quantity_str)
        return int(quantity_float) if quantity_float.is_integer() else quantity_float
    except (ValueError, TypeError):
        return quantity_str


@router.message(F.text.as_("text"))
async def search_handler(message: Message, text: str):
    known_commands = ["Новий список", "Мій список", "🗂️ Архів списків", "👑 Адмін-панель"]
    if text.startswith("/") or text in known_commands:
        return

    if len(text) < 3:
        await message.answer(LEXICON.SEARCH_TOO_SHORT)
        return

    products = await orm_find_products(text)

    if not products:
        await message.answer(LEXICON.SEARCH_NO_RESULTS)
        return

    if len(products) == 1:
        await show_product_card(message, products[0])
    else:
        await message.answer(
            LEXICON.SEARCH_MANY_RESULTS,
            reply_markup=get_search_results_kb(products),
        )


@router.callback_query(F.data.startswith("product:"))
async def show_product_from_button(callback: CallbackQuery):
    product_id = int(callback.data.split(":", 1)[1])

    async with async_session() as session:
        product = await orm_get_product_by_id(session, product_id)
        if product:
            await callback.message.edit_reply_markup(reply_markup=None)
            await show_product_card(callback.message, product)

    await callback.answer()


async def show_product_card(message: Message, product):
    """
    Формує та відправляє картку товару з інформацією про доступність та кнопками дій.
    """
    try:
        stock_quantity = float(product.кількість)
        reserved_quantity = product.відкладено or 0
        available_quantity = stock_quantity - reserved_quantity
        display_available = format_quantity(str(available_quantity))
        int_available = int(available_quantity)
    except (ValueError, TypeError):
        display_available = product.кількість
        int_available = 0

    card_text = LEXICON.PRODUCT_CARD_TEMPLATE.format(
        name=product.назва,
        department=product.відділ,
        group=product.група,
        available=display_available,
        reserved=product.відкладено or 0,
    )

    await message.answer(
        card_text, reply_markup=get_product_actions_kb(product.id, int_available)
    )