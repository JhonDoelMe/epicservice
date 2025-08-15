# epicservice/handlers/user/item_addition.py

import logging
import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from database.engine import async_session
from database.orm import (orm_add_item_to_temp_list, orm_get_product_by_id,
                          orm_get_temp_list_department)
from keyboards.reply import admin_main_kb, cancel_kb, user_main_kb
from lexicon.lexicon import LEXICON
from utils.card_generator import send_or_edit_product_card

logger = logging.getLogger(__name__)
router = Router()

class ItemAdditionStates(StatesGroup):
    waiting_for_quantity = State()

@router.callback_query(F.data.startswith("add_all:"))
async def add_all_callback(callback: CallbackQuery, bot: Bot):
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
async def add_custom_callback(callback: CallbackQuery, state: FSMContext):
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
            await state.update_data(product_id=product.id, card_message_id=callback.message.message_id)
            await callback.message.edit_reply_markup(reply_markup=None)
            prompt_message = await callback.message.answer(
                LEXICON.ENTER_QUANTITY.format(product_name=product.назва),
                reply_markup=cancel_kb, parse_mode=None
            )
            await state.update_data(prompt_message_id=prompt_message.message_id)
            await state.set_state(ItemAdditionStates.waiting_for_quantity)
            await callback.answer()
    except Exception as e:
        logger.error("Неочікувана помилка ініціації додавання товару %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)

@router.message(ItemAdditionStates.waiting_for_quantity, F.text == LEXICON.BUTTON_CANCEL)
async def cancel_quantity_input(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    reply_kb = admin_main_kb if message.from_user.id in ADMIN_IDS else user_main_kb
    await message.answer(LEXICON.CANCEL_ACTION, reply_markup=reply_kb)
    await message.delete()
    await bot.delete_message(message.chat.id, data['prompt_message_id'])
    async with async_session() as session:
        product = await orm_get_product_by_id(session, data['product_id'])
        if product:
            await send_or_edit_product_card(bot, message.chat.id, message.from_user.id, product, data['card_message_id'])

@router.message(ItemAdditionStates.waiting_for_quantity, F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb
    try:
        quantity = int(message.text)
        data = await state.get_data()
        await message.delete()
        await bot.delete_message(message.chat.id, data['prompt_message_id'])

        # ВИПРАВЛЕНО: Спрощена логіка. Ми не надсилаємо тимчасових повідомлень.
        if quantity <= 0:
            # Якщо введено 0, просто відновлюємо картку і повертаємо головну клавіатуру
            await message.answer(LEXICON.CANCEL_ACTION, reply_markup=reply_kb)
            async with async_session() as session:
                product = await orm_get_product_by_id(session, data['product_id'])
                if product:
                    await send_or_edit_product_card(bot, message.chat.id, user_id, product, data['card_message_id'])
            await state.clear()
            return

        product_id = data.get("product_id")
        await orm_add_item_to_temp_list(user_id, product_id, quantity)

        # Надсилаємо ОДНЕ фінальне повідомлення, яке повертає клавіатуру
        await message.answer(f"✅ Додано {quantity} шт. до вашого списку.", reply_markup=reply_kb)

        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if product:
                await send_or_edit_product_card(bot, message.chat.id, user_id, product, data['card_message_id'])
        
    except Exception as e:
        logger.error("Неочікувана помилка в process_quantity для %s: %s", user_id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)
    finally:
        await state.clear()