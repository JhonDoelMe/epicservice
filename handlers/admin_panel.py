from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from keyboards.inline import get_admin_panel_kb
from database.orm import orm_smart_import, orm_clear_all_reservations

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))

class AdminStates(StatesGroup):
    waiting_for_import_file = State()

@router.message(F.text == "👑 Адмін-панель")
async def admin_panel_handler(message: Message):
    await message.answer(
        "Ви в панелі адміністратора. Оберіть дію:",
        reply_markup=get_admin_panel_kb()
    )

@router.callback_query(F.data == "admin:import_products")
async def start_import_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Будь ласка, надішліть мені файл Excel (`.xlsx`) з товарами.")
    await state.set_state(AdminStates.waiting_for_import_file)
    await callback.answer()

@router.message(AdminStates.waiting_for_import_file, F.document)
async def process_import_file(message: Message, state: FSMContext, bot: Bot):
    if not message.document.file_name.endswith('.xlsx'):
        await message.answer("Помилка. Будь ласка, надішліть файл у форматі `.xlsx`.")
        return

    await message.answer("Обробляю файл... Це може зайняти деякий час.")
    
    # Обнуляємо всі резерви перед імпортом
    await orm_clear_all_reservations()

    file_path = f"temp_{message.document.file_id}.xlsx"
    await bot.download(message.document, destination=file_path)

    result_message = await orm_smart_import(file_path)
    
    await message.answer(result_message)
    await state.clear()
    
    import os
    if os.path.exists(file_path):
        os.remove(file_path)

@router.message(AdminStates.waiting_for_import_file)
async def incorrect_import_file(message: Message):
    await message.answer("Будь ласка, надішліть документ (файл Excel).")