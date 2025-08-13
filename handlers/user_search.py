import logging
from typing import Union

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError

from database.engine import async_session
from database.orm import (orm_find_products, orm_get_product_by_id,
                          orm_get_temp_list_item_quantity)
from keyboards.inline import get_product_actions_kb, get_search_results_kb
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)

router = Router()

def format_quantity(quantity_str: str) -> Union[int, float, str]:
    """
    Форматує рядок з кількістю, перетворюючи його на ціле число,
    якщо воно не має дробової частини.

    Args:
        quantity_str: Рядок, що представляє кількість (напр., "15.0" або "15.5").

    Returns:
        Ціле число, число з плаваючою комою або вихідний рядок у разі помилки.
    """
    try:
        quantity_float = float(quantity_str)
        return int(quantity_float) if quantity_float.is_integer() else quantity_float
    except (ValueError, TypeError):
        # Повертаємо вихідний рядок, якщо перетворення неможливе
        return quantity_str

@router.message(F.text)
async def search_handler(message: Message):
    """
    Обробляє текстові повідомлення як пошукові запити, ігноруючи команди та кнопки.
    """
    search_query = message.text
    # Ігноруємо відомі команди та кнопки меню, щоб уникнути їх обробки як пошуку
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

        # Якщо знайдено один товар, одразу показуємо його картку
        if len(products) == 1:
            await show_product_card(message, products[0])
        # Якщо знайдено декілька, пропонуємо вибір
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
                # Видаляємо клавіатуру зі списком товарів і показуємо картку обраного
                await callback.message.edit_reply_markup(reply_markup=None)
                await show_product_card(callback.message, product)
            else:
                logger.warning("Товар з ID %s не знайдено після натискання на кнопку.", product_id)
                await callback.message.edit_text(LEXICON.PRODUCT_NOT_FOUND)
    except (ValueError, IndexError) as e:
        logger.error("Невірний формат product_id у callback'у: %s", callback.data, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    except SQLAlchemyError as e:
        logger.error("Помилка БД при отриманні товару %s: %s", product_id, e, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)


async def show_product_card(message: Message, product) -> None:
    """
    Формує та відправляє інформаційну картку товару.
    Враховує вже відкладені товари та товари в поточному списку користувача.

    Args:
        message: Об'єкт Message або CallbackQuery.message, куди буде надіслано картку.
        product: Об'єкт товару (Product), для якого створюється картка.
    """
    user_id = message.chat.id
    
    try:
        # Кількість цього товару в поточному (незбереженому) списку користувача
        in_temp_list_quantity = await orm_get_temp_list_item_quantity(user_id, product.id)
        
        try:
            stock_quantity = float(product.кількість)
            # Резерви у вже збережених списках
            permanently_reserved = product.відкладено or 0
            
            # Розрахунок реальної доступної кількості
            available_for_user = stock_quantity - permanently_reserved - in_temp_list_quantity
            # Загальна кількість в резерві (збережені + поточний список)
            total_reserved_for_user = permanently_reserved + in_temp_list_quantity

            display_available = format_quantity(str(available_for_user))
            # Кількість для кнопки "Додати все" не може бути дробовою або від'ємною
            int_available_for_button = max(0, int(available_for_user))
            display_total_reserved = format_quantity(str(total_reserved_for_user))

        except (ValueError, TypeError):
            # Якщо кількість в БД задана не числом
            display_available = product.кількість
            int_available_for_button = 0
            display_total_reserved = (product.відкладено or 0) + in_temp_list_quantity

        card_text = LEXICON.PRODUCT_CARD_TEMPLATE.format(
            name=product.назва,
            department=product.відділ,
            group=product.група,
            available=display_available,
            reserved=display_total_reserved,
        )

        await message.answer(
            card_text,
            reply_markup=get_product_actions_kb(product.id, int_available_for_button)
        )
    except Exception as e:
        logger.error("Помилка формування картки товару %s для користувача %s: %s", product.id, user_id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR)