from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import ADMIN_IDS
from keyboards.reply import user_main_kb, admin_main_kb

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обробник команди /start. Визначає, чи є користувач адміном."""
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        await message.answer("Вітаю, Адміністраторе!", reply_markup=admin_main_kb)
    else:
        await message.answer("Вітаю! Я допоможу вам знайти товари та створити списки.", reply_markup=user_main_kb)