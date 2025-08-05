import logging
from aiogram import Router, Bot
from aiogram.types import ErrorEvent

router = Router()

@router.errors()
async def error_handler(event: ErrorEvent, bot: Bot):
    """
    Глобальний обробник помилок. Ловить усі винятки.
    """
    logging.exception(f"Сталася критична помилка в обробнику: {event.exception}")
    
    # Визначаємо, куди відправити повідомлення
    chat_id = None
    if event.update.message:
        chat_id = event.update.message.chat.id
    elif event.update.callback_query:
        chat_id = event.update.callback_query.message.chat.id

    if chat_id:
        await bot.send_message(
            chat_id,
            "😔 Виникла непередбачена помилка.\n"
            "Ми вже отримали сповіщення і працюємо над її вирішенням."
        )