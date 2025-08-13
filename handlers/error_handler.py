import logging
from typing import Optional

from aiogram import Bot, Router
from aiogram.types import ErrorEvent, Message, CallbackQuery
from aiogram.types.base import UNSET
from lexicon.lexicon import LEXICON

# Налаштування логування
logger = logging.getLogger(__name__)

router = Router()

def _extract_user_info(event: ErrorEvent) -> tuple[Optional[int], str]:
    """
    Витягує інформацію про користувача з об'єкта помилки.
    
    Args:
        event: Об'єкт помилки
        
    Returns:
        Кортеж (chat_id, user_info)
    """
    chat_id = None
    user_info = "N/A"
    
    update = event.update
    if isinstance(update.message, Message):
        chat_id = update.message.chat.id
        if update.message.from_user:
            user = update.message.from_user
            user_info = f"user_id={user.id}, username={user.username}"
    elif isinstance(update.callback_query, CallbackQuery) and update.callback_query.message:
        chat_id = update.callback_query.message.chat.id
        if update.callback_query.from_user:
            user = update.callback_query.from_user
            user_info = f"user_id={user.id}, username={user.username}"
    
    return chat_id, user_info

@router.errors()
async def error_handler(event: ErrorEvent, bot: Bot) -> None:
    """
    Глобальний обробник необроблених винятків.
    
    Логує деталі помилки та сповіщає користувача про проблему.
    
    Args:
        event: Об'єкт помилки
        bot: Екземпляр бота
    """
    chat_id, user_info = _extract_user_info(event)
    
    # Логування помилки
    logger.critical(
        "Необроблена помилка у чаті %s (%s): %s",
        chat_id or "UNKNOWN",
        user_info,
        event.exception,
        exc_info=True
    )
    
    # Відправка повідомлення користувачу
    if chat_id and chat_id != UNSET:
        try:
            await bot.send_message(chat_id, LEXICON.UNEXPECTED_ERROR)
        except Exception as e:
            logger.error("Не вдалося відправити повідомлення про помилку: %s", e)