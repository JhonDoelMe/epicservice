# epicservice/utils/card_generator.py

import logging
from typing import Union

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from database.models import Product
from database.orm import (orm_get_temp_list_item_quantity,
                          orm_get_total_temp_reservation_for_product)
from keyboards.inline import get_product_actions_kb
from lexicon.lexicon import LEXICON
from utils.markdown_corrector import escape_markdown

logger = logging.getLogger(__name__)


def format_quantity(quantity_str: str) -> Union[int, float, str]:
    try:
        quantity_float = float(str(quantity_str).replace(',', '.'))
        return int(quantity_float) if quantity_float.is_integer() else quantity_float
    except (ValueError, TypeError):
        return quantity_str


async def send_or_edit_product_card(
    bot: Bot,
    chat_id: int,
    user_id: int,
    product: Product,
    message_id: int = None
):
    """
    Формує та надсилає (або редагує) інформаційну картку товару.

    Args:
        bot: Екземпляр бота.
        chat_id: ID чату для відправки/редагування.
        user_id: ID користувача для розрахунку резервів.
        product: Об'єкт Product.
        message_id: ID повідомлення для редагування. Якщо None, надсилається нове.
    """
    try:
        in_user_temp_list_qty = await orm_get_temp_list_item_quantity(user_id, product.id)
        total_temp_reserved = await orm_get_total_temp_reservation_for_product(product.id)

        try:
            stock_quantity = float(str(product.кількість).replace(',', '.'))
            permanently_reserved = product.відкладено or 0
            available_for_anyone = stock_quantity - permanently_reserved - total_temp_reserved
            int_available_for_button = max(0, int(available_for_anyone))
            display_available = format_quantity(available_for_anyone)
            display_user_reserved = format_quantity(in_user_temp_list_qty)
        except (ValueError, TypeError):
            display_available = product.кількість
            int_available_for_button = 0
            display_user_reserved = in_user_temp_list_qty

        card_text = LEXICON.PRODUCT_CARD_TEMPLATE.format(
            name=escape_markdown(product.назва),
            department=escape_markdown(product.відділ),
            group=escape_markdown(product.група),
            available=escape_markdown(display_available),
            reserved=escape_markdown(display_user_reserved),
        )
        keyboard = get_product_actions_kb(product.id, int_available_for_button)

        if message_id:
            try:
                await bot.edit_message_text(
                    text=card_text,
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise
        else:
            await bot.send_message(chat_id, card_text, reply_markup=keyboard)

    except Exception as e:
        logger.error("Помилка відправки/редагування картки товару %s для %s: %s", product.id, user_id, e, exc_info=True)
        await bot.send_message(chat_id, LEXICON.UNEXPECTED_ERROR)