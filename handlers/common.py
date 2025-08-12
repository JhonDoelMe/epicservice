from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import ADMIN_IDS
from keyboards.reply import admin_main_kb, user_main_kb
from lexicon.lexicon import LEXICON

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обробник команди /start. Визначає, чи є користувач адміном."""
    user_id = message.from_user.id

    if user_id in ADMIN_IDS:
        await message.answer(LEXICON.CMD_START_ADMIN, reply_markup=admin_main_kb)
    else:
        await message.answer(LEXICON.CMD_START_USER, reply_markup=user_main_kb)