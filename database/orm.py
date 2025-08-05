import asyncio
import pandas as pd
from sqlalchemy import delete, select, or_, update

from database.engine import async_engine, sync_session, async_session
from database.models import Base, Product

async def create_tables():
    """Створює таблиці в базі даних, якщо їх не існує."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def _sync_smart_import(file_path: str):
    """
    ПОВНІСТЮ СИНХРОННА функція для обробки файлу та запису в БД.
    """
    try:
        df = pd.read_excel(file_path)
        
        expected_columns_short = ['в', 'г', 'н', 'к']
        if list(df.columns) != expected_columns_short:
            expected_str = ", ".join(expected_columns_short)
            return f"❌ Помилка: назви колонок у файлі неправильні.\n\nОчікується: `{expected_str}`"

        df.rename(columns={'в': 'відділ', 'г': 'група', 'н': 'назва', 'к': 'кількість'}, inplace=True)

        products_to_add = []
        for _, row in df.iterrows():
            if pd.isna(row['назва']) or pd.isna(row['відділ']):
                continue
            products_to_add.append(
                Product(
                    назва=str(row['назва']),
                    відділ=int(row['відділ']),
                    група=str(row['група']),
                    кількість=str(row['кількість'])
                )
            )

        with sync_session() as session:
            session.execute(delete(Product))
            session.add_all(products_to_add)
            session.commit()
        
        return f"✅ Імпорт успішно завершено!\nДодано товарів: {len(products_to_add)}"

    except Exception as e:
        return f"❌ Сталася помилка під час імпорту: {str(e)}"

async def orm_smart_import(file_path: str):
    """
    Асинхронна обгортка, яка викликає синхронну функцію в окремому потоці.
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _sync_smart_import, file_path)
    return result

async def orm_find_products(search_query: str):
    """
    Виконує пошук товарів у базі даних за частковим збігом в назві.
    """
    async with async_session() as session:
        query = (
            select(Product)
            .where(Product.назва.ilike(f'%{search_query}%'))
            .limit(15)
        )
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_product_by_id(product_id: int):
    """Знаходить один товар за його ID."""
    async with async_session() as session:
        query = select(Product).where(Product.id == product_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

async def orm_update_reserved_quantity(items: list):
    """
    Оновлює поле 'відкладено' для товарів у списку.
    Приймає список словників: [{'product_id': id, 'quantity': count}]
    """
    async with async_session() as session:
        for item in items:
            query = select(Product).where(Product.id == item['product_id'])
            result = await session.execute(query)
            product = result.scalar_one_or_none()

            if product:
                new_reserved = (product.відкладено or 0) + item['quantity']
                update_query = (
                    update(Product)
                    .where(Product.id == item['product_id'])
                    .values(відкладено=new_reserved)
                )
                await session.execute(update_query)
        
        await session.commit()

async def orm_clear_all_reservations():
    """Обнуляє поле 'відкладено' для всіх товарів."""
    async with async_session() as session:
        await session.execute(update(Product).values(відкладено=0))
        await session.commit()