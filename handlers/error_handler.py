import logging
from aiogram import Router, F
from aiogram.types import ErrorEvent

router = Router()

@router.errors()
async def error_handler(event: ErrorEvent):
    """
    Глобальний обробник помилок. Ловить усі винятки.
    """
    logging.exception("Сталася критична помилка в обробнику")
    
    # Відправляємо повідомлення користувачу
    await event.update.message.answer(
        "😔 Виникла непередбачена помилка.\n"
        "Ми вже отримали сповіщення і працюємо над її вирішенням."
    )