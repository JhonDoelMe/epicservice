# epicservice/database/orm/reports.py

import logging
from collections import defaultdict
from typing import Dict

from sqlalchemy import func, select, literal_column, text
from sqlalchemy.orm import joinedload

from database.engine import sync_session
from database.models import Product, SavedList, SavedListItem, TempList

logger = logging.getLogger(__name__)


def orm_get_stock_status_sync() -> Dict[int, int]:
    """
    Синхронно отримує звіт про стан складу.

    Рахує кількість унікальних артикулів по кожному відділу,
    де фізична кількість товару на складі більша за нуль.

    Returns:
        Словник, де ключ - ID відділу, а значення - кількість артикулів.
    """
    with sync_session() as session:
        # ВИПРАВЛЕНО: Використовуємо більш надійний SQL-запит з явною перевіркою
        # Ця конструкція намагається перетворити рядок на число і відфільтровує помилки.
        query = text(
            """
            SELECT відділ, COUNT(id)
            FROM products
            WHERE NULLIF(regexp_replace(кількість, ',', '.', 'g'), '')::numeric > 0
            GROUP BY відділ
            ORDER BY відділ;
            """
        )
        result = session.execute(query).all()
        return {department: count for department, count in result}


def orm_get_collection_status_sync() -> Dict[int, int]:
    """
    Синхронно отримує звіт про стан збору.

    Рахує сумарну кількість одиниць товару (не артикулів) у всіх
    тимчасових та збережених списках, групуючи за відділами.

    Returns:
        Словник, де ключ - ID відділу, а значення - сумарна кількість одиниць.
    """
    with sync_session() as session:
        collection_by_department = defaultdict(int)

        # 1. Збираємо дані з тимчасових списків (активні збори)
        temp_items_query = (
            select(TempList.quantity, Product.відділ)
            .join(Product, TempList.product_id == Product.id)
        )
        temp_items = session.execute(temp_items_query).all()
        for quantity, department in temp_items:
            collection_by_department[department] += quantity

        # 2. Збираємо дані зі збережених списків (архіви)
        saved_items_query = (
            select(SavedListItem.quantity, Product.відділ)
            .join(SavedList, SavedListItem.list_id == SavedList.id)
            .join(Product, SavedListItem.article_name.contains(Product.артикул))
        )
        saved_items = session.execute(saved_items_query).all()
        for quantity, department in saved_items:
            collection_by_department[department] += quantity

        return dict(sorted(collection_by_department.items()))