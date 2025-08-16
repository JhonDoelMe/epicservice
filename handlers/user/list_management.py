# epicservice/handlers/user/list_management.py

import logging
import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
# --- ЗМІНА: Додаємо InlineKeyboardMarkup та InlineKeyboardButton ---
from aiogram.types import (CallbackQuery, Message, 
                           InlineKeyboardMarkup, InlineKeyboardButton)
from sqlalchemy.exc import SQLAlchemyError

from config import ADMIN_IDS
from database.orm import orm_clear_temp_list, orm_get_temp_list
from keyboards.inline import (get_confirmation_kb, get_my_list_kb,
                              get_admin_main_kb, get_user_main_kb)
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)
router = Router()

class ListManagementStates(StatesGroup):
    confirm_new_list = State()
    confirm_cancel_list = State()


async def _display_user_list(bot: Bot, chat_id: int, user_id: int):
    """
    Основна логіка для відображення поточного списку користувача.
    """
    try:
        temp_list = await orm_get_temp_list(user_id)
        if not temp_list:
            # --- ЗМІНА: Додаємо кнопку "На головну" для порожнього списку ---
            back_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=LEXICON.BUTTON_BACK_TO_MAIN_MENU,
                    callback_data="main:back"
                )
            ]])
            await bot.send_message(chat_id, LEXICON.EMPTY_LIST, reply_markup=back_kb)
            # --- КІНЕЦЬ ЗМІНИ ---
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
        await bot.send_message(chat_id, LEXICON.UNEXPECTED_ERROR)

@router.callback_query(F.data == "main:back")
async def back_to_main_menu(callback: CallbackQuery):
    """
    Повертає користувача на головний екран, редагуючи поточне повідомлення.
    """
    user_id = callback.from_user.id
    kb = get_admin_main_kb() if user_id in ADMIN_IDS else get_user_main_kb()
    text = LEXICON.CMD_START_ADMIN if user_id in ADMIN_IDS else LEXICON.CMD_START_USER
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception: # Якщо повідомлення не можна редагувати, надсилаємо нове
        await callback.message.answer(text, reply_markup=kb)
        await callback.message.delete() # і видаляємо старе
    finally:
        await callback.answer()


@router.callback_query(F.data == "main:new_list")
async def new_list_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        LEXICON.NEW_LIST_CONFIRM,
        reply_markup=get_confirmation_kb("confirm_new_list", "main:back"),
    )
    await state.set_state(ListManagementStates.confirm_new_list)
    await callback.answer()

@router.callback_query(ListManagementStates.confirm_new_list, F.data == "confirm_new_list")
async def new_list_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.clear()
    try:
        await orm_clear_temp_list(user_id)
        
        # --- ЗМІНА: Залишаємо користувача в режимі пошуку ---
        back_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=LEXICON.BUTTON_BACK_TO_MAIN_MENU,
                callback_data="main:back"
            )
        ]])
        await callback.message.edit_text(
            LEXICON.NEW_LIST_CONFIRMED, 
            reply_markup=back_kb
        )
        # --- КІНЕЦЬ ЗМІНИ ---

    except SQLAlchemyError as e:
        logger.error("Помилка БД при очищенні тимчасового списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await callback.answer()

@router.callback_query(F.data == "main:my_list")
async def my_list_handler(callback: CallbackQuery, bot: Bot):
    await callback.message.delete()
    await _display_user_list(bot, callback.message.chat.id, callback.from_user.id)
    await callback.answer()


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
    await state.clear()
    try:
        await orm_clear_temp_list(user_id)
        await callback.message.delete()
        await callback.message.answer(LEXICON.LIST_CANCELED)
        
        user = callback.from_user
        kb = get_admin_main_kb() if user.id in ADMIN_IDS else get_user_main_kb()
        text = LEXICON.CMD_START_ADMIN if user.id in ADMIN_IDS else LEXICON.CMD_START_USER
        await callback.message.answer(text, reply_markup=kb)
    except SQLAlchemyError as e:
        logger.error("Помилка БД при скасуванні списку для %s: %s", user_id, e, exc_info=True)
        await callback.message.edit_text(LEXICON.UNEXPECTED_ERROR)
    finally:
        await callback.answer()

@router.callback_query(ListManagementStates.confirm_cancel_list, F.data == "cancel_list:no")
async def cancel_list_declined(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await callback.message.delete()
    await _display_user_list(bot, callback.message.chat.id, callback.from_user.id)
    await callback.answer()