# epicservice/handlers/user_search.py

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError

from database.engine import async_session
from database.orm import orm_find_products, orm_get_product_by_id
from keyboards.inline import get_search_results_kb
from lexicon.lexicon import LEXICON
from utils.card_generator import send_or_edit_product_card

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text)
async def search_handler(message: Message, bot: Bot):
    search_query = message.text
    known_commands = {
        LEXICON.BUTTON_NEW_LIST, LEXICON.BUTTON_MY_LIST,
        LEXICON.BUTTON_ARCHIVE, LEXICON.BUTTON_ADMIN_PANEL
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
            await send_or_edit_product_card(bot, message.chat.id, message.from_user.id, products[0])
        else:
            await message.answer(LEXICON.SEARCH_MANY_RESULTS, reply_markup=get_search_results_kb(products))
    except SQLAlchemyError as e:
        logger.error("Помилка пошуку товарів для запиту '%s': %s", search_query, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)

@router.callback_query(F.data.startswith("product:"))
async def show_product_from_button(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    try:
        product_id = int(callback.data.split(":", 1)[1])
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if product:
                await callback.message.edit_reply_markup(reply_markup=None)
                await send_or_edit_product_card(bot, callback.message.chat.id, callback.from_user.id, product)
            else:
                await callback.message.edit_text(LEXICON.PRODUCT_NOT_FOUND)
    except (ValueError, IndexError, SQLAlchemyError) as e:
        logger.error("Помилка БД при отриманні товару: %s", e)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)