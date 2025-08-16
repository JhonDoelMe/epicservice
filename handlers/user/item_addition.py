# epicservice/handlers/user/item_addition.py

import logging
import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
# --- ОСЬ ВАЖЛИВИЙ РЯДОК ---
from aiogram.types import (CallbackQuery, Message, InlineKeyboardButton,
                           InlineKeyboardMarkup)

from database.engine import async_session
from database.orm import (orm_add_item_to_temp_list, orm_get_product_by_id,
                          orm_get_temp_list_department)
from lexicon.lexicon import LEXICON
from utils.card_generator import send_or_edit_product_card
from keyboards.inline import get_quantity_kb

logger = logging.getLogger(__name__)
router = Router()

# --- ЗМІНА: Видаляємо клас FSM, він більше не потрібен ---
# class ItemAdditionStates(StatesGroup):
#     waiting_for_quantity = State()


async def _add_item_logic(callback: CallbackQuery, bot: Bot, quantity: int):
    """
    Допоміжна функція, що інкапсулює логіку додавання товару в список.
    """
    user_id = callback.from_user.id
    try:
        # product_id береться з callback.data
        product_id = int(callback.data.split(":")[1])

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

            # Оновлюємо картку товару, щоб показати актуальні залишки
            await send_or_edit_product_card(bot, callback.message.chat.id, user_id, product, callback.message.message_id)

    except Exception as e:
        logger.error("Неочікувана помилка додавання товару для %s: %s", user_id, e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.callback_query(F.data.startswith("add_all:"))
async def add_all_callback(callback: CallbackQuery, bot: Bot):
    """Обробляє натискання на кнопку 'Додати все'."""
    quantity = int(callback.data.split(":")[2])
    await _add_item_logic(callback, bot, quantity)


# --- НОВИЙ ОБРОБНИК для кнопок з цифрами ---
@router.callback_query(F.data.startswith("add_quantity:"))
async def add_quantity_callback(callback: CallbackQuery, bot: Bot):
    """Обробляє натискання на кнопки швидкого вибору кількості (1-5)."""
    quantity = int(callback.data.split(":")[2])
    await _add_item_logic(callback, bot, quantity)


@router.callback_query(F.data.startswith("add_custom:"))
async def add_custom_callback(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обробляє натискання на кнопку 'Інша кількість'.
    Тепер показує клавіатуру з цифрами.
    """
    try:
        product_id = int(callback.data.split(":", 1)[1])
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return

        # Отримуємо пошуковий запит, щоб зберегти кнопку "Назад до результатів"
        fsm_data = await state.get_data()
        
        # Редагуємо повідомлення, змінюючи клавіатуру на вибір кількості
        await bot.edit_message_text(
            text=callback.message.text, # Текст картки залишаємо без змін
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=get_quantity_kb(product_id), # Ось наша нова клавіатура
        )
        await callback.answer("Оберіть потрібну кількість")

    except Exception as e:
        logger.error("Помилка при виклику меню вибору кількості: %s", e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.callback_query(F.data.startswith("cancel_quantity_input:"))
async def cancel_quantity_input(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """
    Обробляє скасування вибору кількості та повертає початкову картку товару.
    """
    product_id = int(callback.data.split(":", 1)[1])
    fsm_data = await state.get_data()
    
    async with async_session() as session:
        product = await orm_get_product_by_id(session, product_id)
        if product:
            await send_or_edit_product_card(
                bot,
                chat_id=callback.message.chat.id,
                user_id=callback.from_user.id,
                product=product,
                message_id=callback.message.message_id,
                search_query=fsm_data.get('last_query')
            )
    await callback.answer("Скасовано")


# --- ВИДАЛЕНО: Обробник process_quantity більше не потрібен ---
# @router.message(ItemAdditionStates.waiting_for_quantity, F.text.isdigit())
# async def process_quantity(message: Message, state: FSMContext, bot: Bot):
#     ...