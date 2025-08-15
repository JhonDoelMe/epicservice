# epicservice/database/orm/temp_lists.py

import logging
from typing import List, Tuple

from sqlalchemy import delete, func, select, distinct
from sqlalchemy.orm import selectinload

from database.engine import async_session, sync_session
from database.models import Product, TempList
from database.models import SavedList

# Налаштовуємо логер для цього модуля
logger = logging.getLogger(__name__)


# --- Асинхронні функції для роботи з тимчасовими списками ---

async def orm_clear_temp_list(user_id: int):
    """
    Повністю очищує тимчасовий список для конкретного користувача.

    Args:
        user_id: ID користувача, чий список потрібно очистити.
    """
    async with async_session() as session:
        query = delete(TempList).where(TempList.user_id == user_id)
        await session.execute(query)
        await session.commit()


async def orm_add_item_to_temp_list(user_id: int, product_id: int, quantity: int):
    """
    Додає товар до тимчасового списку користувача.

    Якщо товар вже є у списку, його кількість оновлюється (додається).
    Якщо товару немає, створюється новий запис.

    Args:
        user_id: ID користувача.
        product_id: ID товару, що додається.
        quantity: Кількість товару.
    """
    async with async_session() as session:
        query = select(TempList).where(
            TempList.user_id == user_id, TempList.product_id == product_id
        )
        existing_item = await session.scalar(query)

        if existing_item:
            existing_item.quantity += quantity
        else:
            new_item = TempList(
                user_id=user_id, product_id=product_id, quantity=quantity
            )
            session.add(new_item)

        await session.commit()


async def orm_get_temp_list(user_id: int) -> list[TempList]:
    """
    Отримує поточний тимчасовий список користувача з усіма даними про товари.

    Args:
        user_id: ID користувача.

    Returns:
        Список об'єктів TempList з підвантаженими даними з Product.
    """
    async with async_session() as session:
        query = (
            select(TempList)
            .where(TempList.user_id == user_id)
            .options(selectinload(TempList.product))
        )
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_temp_list_department(user_id: int) -> int | None:
    """
    Визначає відділ поточного тимчасового списку користувача.

    Бере перший товар зі списку і повертає номер його відділу.
    Це використовується для перевірки "правила одного відділу".

    Args:
        user_id: ID користувача.

    Returns:
        Номер відділу або None, якщо список порожній.
    """
    async with async_session() as session:
        query = (
            select(TempList)
            .where(TempList.user_id == user_id)
            .options(selectinload(TempList.product))
            .limit(1)
        )
        first_item = await session.scalar(query)
        return first_item.product.відділ if first_item and first_item.product else None


async def orm_get_temp_list_item_quantity(user_id: int, product_id: int) -> int:
    """
    Отримує кількість конкретного товару в тимчасовому списку поточного користувача.

    Args:
        user_id: ID поточного користувача.
        product_id: ID товару.

    Returns:
        Сумарна кількість товару у списку (зазвичай 0 або більше).
    """
    async with async_session() as session:
        query = (
            select(func.sum(TempList.quantity))
            .where(TempList.user_id == user_id, TempList.product_id == product_id)
        )
        quantity = await session.scalar(query)
        return quantity or 0


async def orm_get_total_temp_reservation_for_product(product_id: int) -> int:
    """
    Отримує сумарну кількість товару у всіх тимчасових списках ВСІХ користувачів.

    Args:
        product_id: ID товару.

    Returns:
        Загальна кількість товару в тимчасових резервах.
    """
    async with async_session() as session:
        query = (
            select(func.sum(TempList.quantity))
            .where(TempList.product_id == product_id)
        )
        total_quantity = await session.scalar(query)
        return total_quantity or 0


async def orm_get_users_with_active_lists() -> List[Tuple[int, int]]:
    """
    Знаходить користувачів, які мають активні (незбережені) списки.

    Returns:
        Список кортежів, де кожен кортеж - (user_id, item_count).
    """
    async with async_session() as session:
        query = (
            select(TempList.user_id, func.count(TempList.id).label("item_count"))
            .group_by(TempList.user_id)
            .having(func.count(TempList.id) > 0)
        )
        result = await session.execute(query)
        return result.all()


# --- Синхронні функції для звітів та фонових завдань ---

def orm_get_all_temp_list_items_sync() -> list[TempList]:
    """
    Синхронно отримує всі позиції з усіх тимчасових списків.

    Використовується для формування звіту про залишки, щоб врахувати
    товари, які користувачі додали до списків, але ще не зберегли.

    Returns:
        Список всіх об'єктів TempList з усіх списків.
    """
    with sync_session() as session:
        query = select(TempList)
        result = session.execute(query)
        return result.scalars().all()


def orm_get_all_active_users_sync() -> List[int]:
    """
    Синхронно отримує ID всіх унікальних користувачів, що взаємодіяли з ботом.

    Returns:
        Список унікальних user_id.
    """
    with sync_session() as session:
        users_from_saved = select(distinct(SavedList.user_id))
        users_from_temp = select(distinct(TempList.user_id))

        all_user_ids = set(session.execute(users_from_saved).scalars())
        all_user_ids.update(session.execute(users_from_temp).scalars())

        return list(all_user_ids)