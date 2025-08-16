# epicservice/handlers/user/item_addition.py

import logging
import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_IDS
from database.engine import async_session
from database.orm import (orm_add_item_to_temp_list, orm_get_product_by_id,
                          orm_get_temp_list_department)
from lexicon.lexicon import LEXICON
from utils.card_generator import send_or_edit_product_card

logger = logging.getLogger(__name__)
router = Router()

class ItemAdditionStates(StatesGroup):
    waiting_for_quantity = State()


@router.callback_query(F.data.startswith("add_all:"))
async def add_all_callback(callback: CallbackQuery, bot: Bot):
    # ... (код без змін)
    user_id = callback.from_user.id
    try:
        _, product_id_str, quantity_str = callback.data.split(":")
        product_id = int(product_id_str)
        quantity = int(quantity_str)
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return
            allowed_department = await orm_get_temp_list_department(user_id)
            if allowed_department is not None and product.відділ != allowed_department:
                await callback.answer(LEXICON.DEPARTMENT_MISMATCH.format(department=allowed_department), show_alert=True)
                return
            await orm_add_item_to_temp_list(user_id, product_id, quantity)
            logger.info("Користувач %s додав товар ID %s (кількість: %s) до списку.", user_id, product_id, quantity)
            await callback.answer(f"✅ Додано {quantity} шт.")
            await send_or_edit_product_card(bot, callback.message.chat.id, user_id, product, callback.message.message_id)
            
    except Exception as e:
        logger.error("Неочікувана помилка додавання товару для %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.callback_query(F.data.startswith("add_custom:"))
async def add_custom_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код без змін)
    user_id = callback.from_user.id
    try:
        product_id = int(callback.data.split(":", 1)[1])
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return

            allowed_department = await orm_get_temp_list_department(user_id)
            if allowed_department is not None and product.відділ != allowed_department:
                await callback.answer(LEXICON.DEPARTMENT_MISMATCH.format(department=allowed_department), show_alert=True)
                return
            
            await state.update_data(
                product_id=product.id,
                card_message_id=callback.message.message_id,
                chat_id=callback.message.chat.id
            )

            cancel_input_kb = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text=LEXICON.BUTTON_CANCEL_INPUT,
                        callback_data="cancel_quantity_input"
                    )
                ]]
            )
            await bot.edit_message_text(
                text=LEXICON.ENTER_QUANTITY.format(product_name=product.назва),
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=cancel_input_kb,
                parse_mode=None
            )
            
            await state.set_state(ItemAdditionStates.waiting_for_quantity)
            await callback.answer()

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
             logger.error("Помилка редагування картки в режим вводу: %s", e)
        await callback.answer()
    except Exception as e:
        logger.error("Неочікувана помилка ініціації додавання товару %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.callback_query(ItemAdditionStates.waiting_for_quantity, F.data == "cancel_quantity_input")
async def cancel_quantity_input(callback: CallbackQuery, state: FSMContext, bot: Bot):
    # ... (код без змін)
    data = await state.get_data()
    await state.clear()
    
    async with async_session() as session:
        product = await orm_get_product_by_id(session, data['product_id'])
        if product:
            await send_or_edit_product_card(
                bot,
                chat_id=data['chat_id'],
                user_id=callback.from_user.id,
                product=product,
                message_id=data['card_message_id']
            )
    await callback.answer("Введення скасовано")


@router.message(ItemAdditionStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    try:
        quantity = int(message.text)
        data = await state.get_data()
        
        await message.delete()

        if quantity <= 0:
            await state.clear()
            async with async_session() as session:
                product = await orm_get_product_by_id(session, data['product_id'])
                if product:
                    await send_or_edit_product_card(
                        bot, data['chat_id'], user_id, product, data['card_message_id']
                    )
            return

        product_id = data.get("product_id")
        await orm_add_item_to_temp_list(user_id, product_id, quantity)
        
        # --- ЗМІНА: Замінюємо answer_callback_query на тимчасове повідомлення ---
        sent_message = await bot.send_message(
            chat_id=message.chat.id,
            text=f"✅ Додано {quantity} шт. до вашого списку."
        )
        await asyncio.sleep(2) # Чекаємо 2 секунди
        await bot.delete_message(chat_id=message.chat.id, message_id=sent_message.message_id)
        # --- КІНЕЦЬ ЗМІНИ ---

        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if product:
                await send_or_edit_product_card(
                    bot, data['chat_id'], user_id, product, data['card_message_id']
                )
        
    except Exception as e:
        logger.error("Неочікувана помилка в process_quantity для %s: %s", user_id, e, exc_info=True)
        data = await state.get_data()
        async with async_session() as session:
            product = await orm_get_product_by_id(session, data.get('product_id'))
            if product:
                await send_or_edit_product_card(bot, data.get('chat_id'), user_id, product, data.get('card_message_id'))
    finally:
        await state.clear()