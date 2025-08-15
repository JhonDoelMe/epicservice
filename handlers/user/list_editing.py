# epicservice/handlers/user/list_editing.py

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_IDS
from database.engine import async_session
from database.orm import (orm_delete_temp_list_item, orm_get_product_by_id,
                          orm_get_temp_list,
                          orm_update_temp_list_item_quantity)
from keyboards.inline import get_list_for_editing_kb
from keyboards.reply import admin_main_kb, cancel_kb, user_main_kb
from lexicon.lexicon import LEXICON
# ВИПРАВЛЕНО: Імпортуємо оновлену функцію
from handlers.user.list_management import _display_user_list

# Налаштовуємо логер
logger = logging.getLogger(__name__)

# Створюємо роутер
router = Router()


# Визначаємо стани FSM
class ListEditingStates(StatesGroup):
    editing_list = State()
    waiting_for_new_quantity = State()


async def show_list_in_edit_mode(bot: Bot, chat_id: int, message_id: int, user_id: int):
    """
    Допоміжна функція для відображення списку в режимі редагування.
    """
    temp_list = await orm_get_temp_list(user_id)

    if not temp_list:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=LEXICON.EMPTY_LIST)
        return

    department_id = temp_list[0].product.відділ
    header = f"{LEXICON.LIST_EDIT_MODE_TITLE} (Відділ: {department_id})\n\n{LEXICON.LIST_EDIT_PROMPT}"

    try:
        await bot.edit_message_text(
            text=header,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=get_list_for_editing_kb(temp_list)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error("Помилка редагування повідомлення в режим редагування: %s", e)


# --- Сценарій редагування списку ---

@router.callback_query(F.data == "edit_list:start")
async def start_list_editing_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(ListEditingStates.editing_list)
    await state.update_data(edit_list_message_id=callback.message.message_id)
    await show_list_in_edit_mode(bot, callback.message.chat.id, callback.message.message_id, callback.from_user.id)
    await callback.answer("Режим редагування увімкнено")


@router.callback_query(ListEditingStates.editing_list, F.data.startswith("edit_item:"))
async def edit_item_handler(callback: CallbackQuery, state: FSMContext):
    try:
        product_id = int(callback.data.split(":", 1)[1])
        async with async_session() as session:
            product = await orm_get_product_by_id(session, product_id)
            if not product:
                await callback.answer(LEXICON.PRODUCT_NOT_FOUND, show_alert=True)
                return

        await state.update_data(product_id=product.id, product_name=product.назва, article=product.артикул)
        prompt_message = await callback.message.answer(
            text=LEXICON.EDIT_ITEM_QUANTITY_PROMPT.format(product_name=product.назва),
            reply_markup=cancel_kb,
            parse_mode=None
        )
        await state.update_data(prompt_message_id=prompt_message.message_id)
        await state.set_state(ListEditingStates.waiting_for_new_quantity)
        await callback.answer()

    except Exception as e:
        logger.error("Помилка при виборі товару для редагування: %s", e, exc_info=True)
        await callback.answer(LEXICON.UNEXPECTED_ERROR, show_alert=True)


@router.message(ListEditingStates.waiting_for_new_quantity, F.text.isdigit())
async def process_new_quantity_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    try:
        new_quantity = int(message.text)
        data = await state.get_data()
        product_id = data.get("product_id")
        edit_list_message_id = data.get("edit_list_message_id")

        if new_quantity > 0:
            await orm_update_temp_list_item_quantity(user_id, product_id, new_quantity)
        else:
            await orm_delete_temp_list_item(user_id, product_id)

        await show_list_in_edit_mode(bot, message.chat.id, edit_list_message_id, user_id)
        
    except Exception as e:
        logger.error("Помилка при оновленні кількості: %s", e, exc_info=True)
        await message.answer(LEXICON.UNEXPECTED_ERROR)
    finally:
        data = await state.get_data()
        await message.delete()
        await bot.delete_message(message.chat.id, data['prompt_message_id'])
        await state.set_state(ListEditingStates.editing_list)


@router.callback_query(ListEditingStates.editing_list, F.data == "edit_list:finish")
async def finish_list_editing_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await callback.message.delete()
    
    # ВИПРАВЛЕНО: Викликаємо оновлену функцію з правильним контекстом
    await _display_user_list(bot, callback.message.chat.id, callback.from_user.id)
    
    await callback.answer("Редагування завершено")