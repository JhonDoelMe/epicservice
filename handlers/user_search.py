# epicservice/handlers/user_search.py

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError
from aiogram.exceptions import TelegramBadRequest

from database.engine import async_session
from database.orm import orm_find_products, orm_get_product_by_id
from keyboards.inline import get_search_results_kb
from lexicon.lexicon import LEXICON
from utils.card_generator import send_or_edit_product_card

logger = logging.getLogger(__name__)
router = Router()

class SearchStates(StatesGroup):
    showing_results = State()


@router.message(F.text)
async def search_handler(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    
    search_query = message.text
    
    # Спочатку перевіряємо, чи це не команда з клавіатури
    known_commands = {
        LEXICON.BUTTON_NEW_LIST, LEXICON.BUTTON_MY_LIST,
        LEXICON.BUTTON_ARCHIVE, LEXICON.BUTTON_ADMIN_PANEL,
    }
    if search_query.startswith("/") or search_query in known_commands:
        # Якщо це команда, нічого не робимо, щоб її обробив інший хендлер
        return

    # --- ЗМІНА: Видаляємо повідомлення користувача із запитом ---
    try:
        await message.delete()
    except TelegramBadRequest:
        # Ігноруємо помилку, якщо бот не має прав на видалення
        logger.warning("Не вдалося видалити пошуковий запит користувача.")

    # Тепер виконуємо решту логіки
    if len(search_query) < 3:
        # Надсилаємо тимчасове повідомлення, яке зникне
        await message.answer(LEXICON.SEARCH_TOO_SHORT, reply_markup=None)
        return
        
    try:
        products = await orm_find_products(search_query)
        if not products:
            await message.answer(LEXICON.SEARCH_NO_RESULTS, reply_markup=None)
            return
            
        if len(products) == 1:
            await send_or_edit_product_card(bot, message.chat.id, message.from_user.id, products[0])
        else:
            await state.set_state(SearchStates.showing_results)
            await state.update_data(last_query=search_query)
            
            await message.answer(
                LEXICON.SEARCH_MANY_RESULTS, 
                reply_markup=get_search_results_kb(products)
            )
            
    except SQLAlchemyError as e:
        logger.error("Помилка пошуку товарів для запиту '%s': %s", search_query, e)
        await message.answer(LEXICON.UNEXPECTED_ERROR)


@router.callback_query(F.data.startswith("product:"))
async def show_product_from_button(callback: CallbackQuery, bot: Bot, state: FSMContext):
    # ... (код без змін) ...
    await callback.answer()
    try:
        product_id = int(callback.data.split(":", 1)[1])
        
        fsm_data = await state.get_data()
        last_query = fsm_data.get('last_query')
        
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if product:
                try:
                    await callback.message.delete()
                except TelegramBadRequest as e:
                    logger.warning("Не вдалося видалити повідомлення з результатами пошуку: %s", e)

                await send_or_edit_product_card(
                    bot=bot, 
                    chat_id=callback.message.chat.id, 
                    user_id=callback.from_user.id, 
                    product=product,
                    search_query=last_query
                )
            else:
                await callback.message.edit_text(LEXICON.PRODUCT_NOT_FOUND)
                
    except (ValueError, IndexError, SQLAlchemyError) as e:
        logger.error("Помилка БД при отриманні товару: %s", e)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)


@router.callback_query(SearchStates.showing_results, F.data == "back_to_results")
async def back_to_results_handler(callback: CallbackQuery, state: FSMContext):
    # ... (код без змін) ...
    fsm_data = await state.get_data()
    last_query = fsm_data.get('last_query')

    if not last_query:
        from handlers.user.list_management import back_to_main_menu
        await back_to_main_menu(callback)
        await callback.answer("Помилка: запит не знайдено", show_alert=True)
        return

    products = await orm_find_products(last_query)
    
    await callback.message.edit_text(
        LEXICON.SEARCH_MANY_RESULTS,
        reply_markup=get_search_results_kb(products)
    )
    await callback.answer()