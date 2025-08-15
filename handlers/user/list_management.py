# epicservice/handlers/user/list_management.py

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, Message)
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS
from database.orm import orm_clear_temp_list, orm_get_temp_list
from keyboards.inline import get_confirmation_kb, get_my_list_kb
from keyboards.reply import admin_main_kb, user_main_kb
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)
router = Router()

class ListManagementStates(StatesGroup):
    confirm_new_list = State()
    confirm_cancel_list = State()

# ВИПРАВЛЕНО: Функція тепер приймає ID і об'єкт бота
async def _display_user_list(bot: Bot, chat_id: int, user_id: int):
    """
    Основна логіка для відображення поточного списку користувача.
    """
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb
    try:
        temp_list = await orm_get_temp_list(user_id)
        if not temp_list:
            await bot.send_message(chat_id, LEXICON.EMPTY_LIST, reply_markup=reply_kb)
            return

        department_id = temp_list[0].product.відділ
        header = [f"*Ваш поточний список (Відділ: {department_id}):*"]
        list_items = [f"`{item.product.артикул}` - *{item.quantity}* шт." for item in temp_list]

        MAX_TELEGRAM_MESSAGE_LENGTH = 4096
        parts, current_part = [], "\n".join(header)

        for line in list_items:
            if len(current_part) + len(line) + 1 > MAX_TELEGRAM_MESSAGE_LENGTH:
                parts.append(current_part)
                current_part = line
            else:
                current_part += "\n" + line
        parts.append(current_part)

        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                await bot.send_message(chat_id, part, reply_markup=get_my_list_kb())
            else:
                await bot.send_message(chat_id, part)
    except Exception as e:
        logger.error("Помилка відображення списку для %s: %s", user_id, e, exc_info=True)
        await bot.send_message(chat_id, LEXICON.UNEXPECTED_ERROR, reply_markup=reply_kb)

# --- Сценарії ---

@router.message(F.text == LEXICON.BUTTON_NEW_LIST)
async def new_list_handler(message: Message, state: FSMContext):
    await message.answer(
        LEXICON.NEW_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("confirm_new_list", "cancel_new_list"),
    )
    await state.set_state(ListManagementStates.confirm_new_list)

@router.callback_query(ListManagementStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
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
    await state.clear()
    await callback.message.edit_text(LEXICON.ACTION_CANCELED)
    await callback.answer()

@router.message(F.text == LEXICON.BUTTON_MY_LIST)
async def my_list_handler(message: Message, bot: Bot):
    # ВИПРАВЛЕНО: Викликаємо оновлену функцію
    await _display_user_list(bot, message.chat.id, message.from_user.id)

@router.callback_query(F.data == "cancel_list:confirm")
async def cancel_list_confirm_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        LEXICON.CANCEL_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("cancel_list:yes", "cancel_list:no")
    )
    await state.set_state(ListManagementStates.confirm_cancel_list)
    await callback.answer()

@router.callback_query(ListManagementStates.confirm_cancel_list, F.data == "cancel_list:yes")
async def cancel_list_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    reply_kb = admin_main_kb if user_id in ADMIN_IDS else user_main_kb
    await state.clear()
    try:
        await orm_clear_temp_list(user_id)
        await callback.message.delete()
        await callback.message.answer(LEXICON.LIST_CANCELED, reply_markup=reply_kb)
    except SQLAlchemyError as e:
        logger.error("Помилка БД при скасуванні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await callback.answer()

@router.callback_query(ListManagementStates.confirm_cancel_list, F.data == "cancel_list:no")
async def cancel_list_declined(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await callback.message.delete()
    # ВИПРАВЛЕНО: Викликаємо оновлену функцію з правильним контекстом
    await _display_user_list(bot, callback.message.chat.id, callback.from_user.id)
    await callback.answer()