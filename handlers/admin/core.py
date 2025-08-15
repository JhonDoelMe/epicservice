# epicservice/handlers/admin/core.py

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from database.orm import orm_delete_all_saved_lists_sync
from keyboards.inline import get_admin_panel_kb, get_confirmation_kb
from lexicon.lexicon import LEXICON

# Налаштовуємо логер для цього модуля
logger = logging.getLogger(__name__)

# Створюємо роутер, специфічний для цього блоку адмін-функцій
router = Router()
# Встановлюємо фільтр, щоб ці обробники реагували лише на повідомлення від адмінів
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


# Визначаємо стани FSM, що використовуються у цьому модулі
class AdminCoreStates(StatesGroup):
    confirm_delete_all_lists = State()


# --- Обробники входу в адмін-панель ---

@router.message(F.text == "👑 Адмін-панель")
async def admin_panel_handler(message: Message):
    """
    Обробник для кнопки '👑 Адмін-панель' на головній клавіатурі.
    Надсилає привітання та основну клавіатуру адмін-панелі.
    """
    await message.answer(
        LEXICON.ADMIN_PANEL_GREETING,
        reply_markup=get_admin_panel_kb()
    )


@router.callback_query(F.data == "admin:main")
async def admin_panel_callback_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки 'Назад до адмін-панелі'.
    Скидає стан FSM та повертає головне меню адмінки.
    """
    await state.clear()
    await callback.message.edit_text(
        LEXICON.ADMIN_PANEL_GREETING,
        reply_markup=get_admin_panel_kb()
    )
    await callback.answer()


# --- Сценарій видалення всіх списків ---

@router.callback_query(F.data == "admin:delete_all_lists")
async def delete_all_lists_confirm_handler(callback: CallbackQuery, state: FSMContext):
    """
    Перший крок сценарію видалення. Запитує підтвердження у адміністратора.
    """
    await callback.message.edit_text(
        LEXICON.DELETE_ALL_LISTS_CONFIRM,
        reply_markup=get_confirmation_kb(
            "confirm_delete_all_yes", "confirm_delete_all_no"
        ),
    )
    await state.set_state(AdminCoreStates.confirm_delete_all_lists)
    await callback.answer()


@router.callback_query(AdminCoreStates.confirm_delete_all_lists, F.data == "confirm_delete_all_yes")
async def delete_all_lists_confirmed_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обробляє позитивне підтвердження. Викликає ORM-функцію для видалення.
    """
    await state.clear()
    
    # Виконуємо синхронну блокуючу операцію в окремому потоці
    loop = asyncio.get_running_loop()
    deleted_count = await loop.run_in_executor(None, orm_delete_all_saved_lists_sync)
    
    if deleted_count > 0:
        await callback.message.edit_text(
            LEXICON.DELETE_ALL_LISTS_SUCCESS.format(count=deleted_count)
        )
    else:
        await callback.message.edit_text(LEXICON.NO_LISTS_TO_DELETE)

    # Повертаємо адміна до головного меню
    await callback.message.answer(
        LEXICON.ADMIN_PANEL_GREETING,
        reply_markup=get_admin_panel_kb()
    )
    await callback.answer("Операцію завершено", show_alert=True)


@router.callback_query(AdminCoreStates.confirm_delete_all_lists, F.data == "confirm_delete_all_no")
async def delete_all_lists_cancelled_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обробляє скасування дії. Повертає адміністратора до головного меню.
    """
    await state.clear()
    await callback.message.edit_text(LEXICON.DELETE_ALL_LISTS_CANCELLED)
    
    # Повертаємо адміна до головного меню
    await callback.message.answer(
        LEXICON.ADMIN_PANEL_GREETING,
        reply_markup=get_admin_panel_kb()
    )
    await callback.answer()