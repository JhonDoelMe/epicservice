import json
import logging

from aiogram import Bot, Router
from aiogram.types import ErrorEvent

from lexicon.lexicon import LEXICON

router = Router()


@router.errors()
async def error_handler(event: ErrorEvent, bot: Bot):
    """
    Глобальний обробник помилок. Ловить усі винятки.
    """
    chat_id = None
    user_info = "N/A"

    if event.update.message:
        chat_id = event.update.message.chat.id
        if event.update.message.from_user:
            user_info = f"user_id={event.update.message.from_user.id}, username={event.update.message.from_user.username}"

    elif event.update.callback_query:
        chat_id = event.update.callback_query.message.chat.id
        if event.update.callback_query.from_user:
            user_info = f"user_id={event.update.callback_query.from_user.id}, username={event.update.callback_query.from_user.username}"

    update_json = json.dumps(
        event.update.model_dump(exclude_none=True), indent=2, ensure_ascii=False
    )

    logging.exception(
        f"Критична помилка!\n"
        f"User: {user_info}\n"
        f"Exception: {event.exception}\n"
        f"Update object:\n{update_json}"
    )

    if chat_id:
        await bot.send_message(chat_id, LEXICON.UNEXPECTED_ERROR)