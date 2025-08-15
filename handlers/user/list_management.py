# epicservice/handlers/user/list_management.py

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS
from database.orm import orm_clear_temp_list, orm_get_temp_list
from keyboards.inline import get_confirmation_kb
from keyboards.reply import admin_main_kb, user_main_kb
from lexicon.lexicon import LEXICON

# Налаштовуємо логер для цього модуля
logger = logging.getLogger(__name__)

# Створюємо роутер для цього функціонального блоку
router = Router()


# Визначаємо стани FSM, що використовуються у цьому модулі
class ListManagementStates(StatesGroup):
    confirm_new_list = State()


# --- Сценарій створення нового списку ---

@router.message(F.text == LEXICON.BUTTON_NEW_LIST)
async def new_list_handler(message: Message, state: FSMContext):
    """
    Починає сценарій створення нового списку, запитуючи у користувача підтвердження.
    """
    await message.answer(
        LEXICON.NEW_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("confirm_new_list", "cancel_new_list"),
    )
    await state.set_state(ListManagementStates.confirm_new_list)


@router.callback_query(ListManagementStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
    """
    Обробляє підтвердження створення нового списку. Очищує старий тимчасовий список.
    """
    user_id = callback.from_user.id
    await state.clear()
    try:
        await orm_clear_temp_list(user_id)
        await callback.message.edit_text(LEXICON.NEW_LIST_CONFIRMED)
    except SQLAlchemyError as e:
        logger.error("Помилка БД при очищенні тимчасового списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await callback.answer()


@router.callback_query(ListManagementStates.confirm_new_list, F.data == "cancel_new_list")
async def new_list_canceled(callback: CallbackQuery, state: FSMContext):
    """
    Обробляє скасування створення нового списку.
    """
    await state.clear()
    await callback.message.edit_text(LEXICON.ACTION_CANCELED)
    await callback.answer()


# --- Сценарій перегляду поточного списку ---

@router.message(F.text == LEXICON.BUTTON_MY_LIST)
async def my_list_handler(message: Message):
    """
    Відображає поточний список товарів користувача.

    Має захист від занадто довгих повідомлень, розбиваючи список на частини,
    якщо він перевищує ліміт Telegram.
    """
    user_id = message.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb

    try:
        temp_list = await orm_get_temp_list(user_id)
        if not temp_list:
            await message.answer(LEXICON.EMPTY_LIST, reply_markup=reply_kb)
            return

        department_id = temp_list[0].product.відділ

        header = [f"*Ваш поточний список (Відділ: {department_id}):*"]
        list_items = [
            f"`{item.product.артикул}` - *{item.quantity}* шт."
            for item in temp_list
        ]

        # Логіка для розбиття довгих повідомлень
        MAX_TELEGRAM_MESSAGE_LENGTH = 4096
        parts = []
        current_part = "\n".join(header)

        for line in list_items:
            if len(current_part) + len(line) + 1 > MAX_TELEGRAM_MESSAGE_LENGTH:
                parts.append(current_part)
                current_part = line  # Нова частина починається з цього рядка
            else:
                current_part += "\n" + line

        parts.append(current_part)

        # Відправляємо всі частини повідомлення
        for i, part in enumerate(parts):
            # Кнопку збереження додаємо тільки до останньої частини
            if i == len(parts) - 1:
                save_button = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=LEXICON.SAVE_LIST_BUTTON, callback_data="save_list")]
                ])
                await message.answer(part, reply_markup=save_button)
            else:
                await message.answer(part)

        await message.answer(LEXICON.FORGET_NOT_TO_SAVE, reply_markup=reply_kb)

    except Exception as e:
        logger.error("Помилка отримання списку для користувача %s: %s", user_id, e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)