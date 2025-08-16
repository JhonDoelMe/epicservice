# epicservice/utils/list_processor.py

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from config import ARCHIVES_PATH
from database.orm import (orm_add_saved_list, orm_clear_temp_list,
                          orm_get_product_by_id, orm_get_temp_list,
                          orm_update_reserved_quantity)
from datetime import datetime

logger = logging.getLogger(__name__)


async def _save_list_to_excel(
    items: List[Dict[str, Any]],
    user_id: int,
    prefix: str = ""
) -> Optional[str]:
    """
    Зберігає список товарів у файл Excel.
    (Ця функція перенесена з list_saving.py для централізації).
    """
    if not items:
        return None
    try:
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
        # Використовуємо назву, що не залежить від вмісту, для універсальності
        file_name = f"{prefix}list_{timestamp}.xlsx"
        archive_dir = os.path.join(ARCHIVES_PATH, f"user_{user_id}")
        os.makedirs(archive_dir, exist_ok=True)
        file_path = os.path.join(archive_dir, file_name)
        df = pd.DataFrame(items)
        df.to_excel(file_path, index=False, header=['Артикул', 'Кількість'])
        logger.info("Файл успішно збережено: %s", file_path)
        return file_path
    except Exception as e:
        logger.error("Помилка збереження Excel файлу для користувача %s: %s", user_id, e, exc_info=True)
        return None


async def process_and_save_list(
    session: AsyncSession,
    user_id: int
) -> Tuple[Optional[str], Optional[str]]:
    """
    Централізована функція для обробки та збереження тимчасового списку.

    Виконує всю бізнес-логіку: перевіряє залишки, оновлює резерви,
    створює файли та зберігає дані в БД.

    Args:
        session: Активна асинхронна сесія SQLAlchemy.
        user_id: ID користувача, чий список обробляється.

    Returns:
        Кортеж із двох елементів: (шлях_до_основного_файлу, шлях_до_файлу_лишків).
        Якщо файл не було створено, відповідне значення буде None.
    """
    temp_list = await orm_get_temp_list(user_id)
    if not temp_list:
        return None, None

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
        
        # Резервуємо повну кількість, яку хоче користувач
        reservation_updates.append({"product_id": product.id, "quantity": item.quantity})

        if item.quantity <= available:
            in_stock_items.append({"артикул": product.артикул, "кількість": item.quantity})
        else:
            if available > 0:
                in_stock_items.append({"артикул": product.артикул, "кількість": available})
            surplus_items.append({"артикул": product.артикул, "кількість": item.quantity - available})

    # Оновлюємо резерви в БД
    if reservation_updates:
        await orm_update_reserved_quantity(session, reservation_updates)

    # Створюємо файли Excel
    main_list_path = await _save_list_to_excel(in_stock_items, user_id)
    surplus_list_path = await _save_list_to_excel(surplus_items, user_id, "лишки_")

    # Зберігаємо інформацію про основний список в архіві БД
    if main_list_path and in_stock_items:
        db_items = [{"article_name": p.product.назва, "quantity": p.quantity} for p in temp_list]
        await orm_add_saved_list(session, user_id, os.path.basename(main_list_path), main_list_path, db_items)

    # Очищуємо тимчасовий список
    await orm_clear_temp_list(user_id)

    return main_list_path, surplus_list_path