import logging
import re
from typing import Union

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError

from database.engine import async_session
from database.orm import (orm_find_products, orm_get_product_by_id,
                          orm_get_temp_list_item_quantity)
from keyboards.inline import get_product_actions_kb, get_search_results_kb
from lexicon.lexicon import LEXICON
# --- ЗМІНЕНО ІМПОРТ ---
from utils.markdown_corrector import escape_markdown

logger = logging.getLogger(__name__)

router = Router()

# Функцію escape_markdown звідси видалено, бо вона тепер в окремому файлі

def format_quantity(quantity_str: str) -> Union[int, float, str]:
    """
    Форматує рядок з кількістю.
    """
    try:
        quantity_float = float(str(quantity_str).replace(',', '.'))
        return int(quantity_float) if quantity_float.is_integer() else quantity_float
    except (ValueError, TypeError):
        return quantity_str

@router.message(F.text)
async def search_handler(message: Message):
    """
    Обробляє текстові повідомлення як пошукові запити.
    """
    search_query = message.text
    known_commands = {
        LEXICON.BUTTON_NEW_LIST,
        LEXICON.BUTTON_MY_LIST,
        LEXICON.BUTTON_ARCHIVE,
        LEXICON.BUTTON_ADMIN_PANEL
    }
    if search_query.startswith("/") or search_query in known_commands:
        return

    if len(search_query) < 3:
        await message.answer(LEXICON.SEARCH_TOO_SHORT)
        return

    try:
        products = await orm_find_products(search_query)
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
    except SQLAlchemyError as e:
        logger.error("Помилка пошуку товарів для запиту '%s': %s", search_query, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)

@router.callback_query(F.data.startswith("product:"))
async def show_product_from_button(callback: CallbackQuery):
    """
    Обробляє натискання на кнопку з товаром зі списку результатів пошуку.
    """
    await callback.answer()
    try:
        product_id = int(callback.data.split(":", 1)[1])
        
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if product:
                await callback.message.edit_reply_markup(reply_markup=None)
                await show_product_card(callback.message, product)
            else:
                await callback.message.edit_text(LEXICON.PRODUCT_NOT_FOUND)
    except (ValueError, IndexError):
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    except SQLAlchemyError as e:
        logger.error("Помилка БД при отриманні товару %s: %s", callback.data.split(":", 1)[1], e)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)

async def show_product_card(message: Message, product) -> None:
    """
    Формує та відправляє інформаційну картку товару.
    """
    user_id = message.chat.id
    
    try:
        in_temp_list_quantity = await orm_get_temp_list_item_quantity(user_id, product.id)
        
        try:
            stock_quantity = float(str(product.кількість).replace(',', '.'))
            permanently_reserved = product.відкладено or 0
            available_for_user = stock_quantity - permanently_reserved - in_temp_list_quantity
            total_reserved_for_user = permanently_reserved + in_temp_list_quantity
            display_available = format_quantity(available_for_user)
            int_available_for_button = max(0, int(available_for_user))
            display_total_reserved = format_quantity(total_reserved_for_user)
        except (ValueError, TypeError):
            display_available = product.кількість
            int_available_for_button = 0
            display_total_reserved = (product.відкладено or 0) + in_temp_list_quantity

        card_text = LEXICON.PRODUCT_CARD_TEMPLATE.format(
            name=escape_markdown(product.назва),
            department=escape_markdown(product.відділ),
            group=escape_markdown(product.група),
            available=escape_markdown(display_available),
            reserved=escape_markdown(display_total_reserved),
        )

        await message.answer(
            card_text,
            reply_markup=get_product_actions_kb(product.id, int_available_for_button)
        )
    except Exception as e:
        logger.error("Помилка формування картки товару %s для користувача %s: %s", product.id, user_id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR)