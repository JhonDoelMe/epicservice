# epicservice/database/orm/users.py

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

# --- ЗМІНА: Видаляємо імпорт sync_session ---
from database.engine import async_session
from database.models import User

logger = logging.getLogger(__name__)


async def orm_upsert_user(user_id: int, username: str | None, first_name: str):
    """Додає нового користувача або оновлює дані існуючого."""
    async with async_session() as session:
        stmt = insert(User).values(id=user_id, username=username, first_name=first_name)
        stmt = stmt.on_conflict_do_update(index_elements=['id'], set_={'username': username, 'first_name': first_name})
        await session.execute(stmt)
        await session.commit()


# --- ЗМІНА: Функція перероблена на асинхронну ---
async def orm_get_all_users_async() -> List[int]:
    """Асинхронно отримує ID всіх зареєстрованих користувачів для розсилки."""
    async with async_session() as session:
        query = select(User.id)
        result = await session.execute(query)
        return list(result.scalars().all())