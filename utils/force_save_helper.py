# epicservice/utils/force_save_helper.py

import logging
import os

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.exc import SQLAlchemyError

from database.engine import async_session
from database.orm import (orm_add_saved_list, orm_clear_temp_list,
                          orm_get_product_by_id, orm_get_temp_list,
                          orm_update_reserved_quantity)
from handlers.user.list_saving import _save_list_to_excel
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)


async def force_save_user_list(user_id: int, bot: Bot) -> bool:
    """
    Примусово зберігає тимчасовий список вказаного користувача.

    Ця функція повторює логіку звичайного збереження, але ініціюється
    адміністратором і надсилає результат (файли) безпосередньо користувачу.

    Args:
        user_id: ID користувача, чий список потрібно зберегти.
        bot: Екземпляр бота для надсилання повідомлень/файлів.

    Returns:
        True, якщо збереження пройшло успішно, інакше False.
    """
    try:
        async with async_session() as session:
            async with session.begin():
                temp_list = await orm_get_temp_list(user_id)
                if not temp_list:
                    return True  # Список порожній, вважаємо операцію успішною

                in_stock_items, surplus_items, reservation_updates = [], [], []

                for item in temp_list:
                    product = await orm_get_product_by_id(session, item.product_id, for_update=True)
                    if not product:
                        continue

                    try:
                        stock_qty = float(str(product.кількість).replace(',', '.'))
                    except (ValueError, TypeError):
                        stock_qty = 0
                    
                    available = stock_qty - (product.відкладено or 0)
                    item_for_excel = {"артикул": product.артикул, "кількість": 0}

                    # --- ВИПРАВЛЕННЯ ЛОГІКИ РЕЗЕРВУВАННЯ ---
                    # Ми резервуємо повну кількість, яку хоче користувач,
                    # щоб логіка відповідала user-side збереженню.
                    reservation_updates.append({"product_id": product.id, "quantity": item.quantity})

                    if item.quantity <= available:
                        # Якщо товару вистачає, він йде в основний файл
                        item_for_excel["кількість"] = item.quantity
                        in_stock_items.append(item_for_excel)
                    else:
                        # Якщо товару не вистачає
                        if available > 0:
                            # Частина, що є, йде в основний файл
                            item_for_excel["кількість"] = available
                            in_stock_items.append(item_for_excel)
                        # Різниця йде у файл лишків
                        surplus_items.append({
                            "артикул": product.артикул, 
                            "кількість": item.quantity - available
                        })
                    # --- КІНЕЦЬ ВИПРАВЛЕННЯ ---

                if reservation_updates:
                    await orm_update_reserved_quantity(session, reservation_updates)

                file_path = await _save_list_to_excel(in_stock_items, user_id)

                if file_path and in_stock_items:
                    db_items = [{"article_name": p.product.назва, "quantity": p.quantity} for p in temp_list]
                    await orm_add_saved_list(session, user_id, os.path.basename(file_path), file_path, db_items)

                await orm_clear_temp_list(user_id)

            # --- Надсилання файлів користувачу після успішної транзакції ---
            if 'file_path' in locals() and file_path and in_stock_items:
                await bot.send_document(user_id, FSInputFile(file_path), caption=LEXICON.MAIN_LIST_SAVED)
            if surplus_items:
                surplus_path = await _save_list_to_excel(surplus_items, user_id, "лишки_")
                if surplus_path:
                    await bot.send_document(user_id, FSInputFile(surplus_path), caption=LEXICON.SURPLUS_LIST_CAPTION)
                    os.remove(surplus_path)
        
        return True

    except (SQLAlchemyError, ValueError) as e:
        logger.error("Помилка транзакції при примусовому збереженні для %s: %s", user_id, e, exc_info=True)
        await bot.send_message(user_id, LEXICON.TRANSACTION_ERROR)
        return False
    except Exception as e:
        logger.error("Неочікувана помилка при примусовому збереженні для %s: %s", user_id, e, exc_info=True)
        await bot.send_message(user_id, LEXICON.UNEXPECTED_ERROR)
        return False