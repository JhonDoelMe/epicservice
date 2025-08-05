import asyncio
import pandas as pd
from sqlalchemy import delete, select, or_, update

from database.engine import async_engine, sync_session, async_session
from database.models import Base, Product, SavedList, SavedListItem

async def create_tables():
    """Створює всі таблиці в базі даних."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Функції імпорту (без змін) ---
def _sync_smart_import(file_path: str):
    try:
        df = pd.read_excel(file_path)
        expected_columns_short = ['в', 'г', 'н', 'к']
        if list(df.columns) != expected_columns_short:
            return f"❌ Помилка: назви колонок неправильні. Очікується: `в, г, н, к`"
        df.rename(columns={'в': 'відділ', 'г': 'група', 'н': 'назва', 'к': 'кількість'}, inplace=True)
        products_to_add = [Product(**row.to_dict()) for _, row in df.iterrows() if pd.notna(row['назва']) and pd.notna(row['відділ'])]
        with sync_session() as session:
            session.execute(delete(Product))
            session.add_all(products_to_add)
            session.commit()
        return f"✅ Імпорт завершено! Додано товарів: {len(products_to_add)}"
    except Exception as e:
        return f"❌ Сталася помилка: {str(e)}"

async def orm_smart_import(file_path: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_smart_import, file_path)

# --- Функції пошуку (без змін) ---
async def orm_find_products(search_query: str):
    async with async_session() as session:
        query = select(Product).where(Product.назва.ilike(f'%{search_query}%')).limit(15)
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_product_by_id(product_id: int):
    async with async_session() as session:
        return await session.get(Product, product_id)

# --- Функції резервування (без змін) ---
async def orm_update_reserved_quantity(items: list):
    async with async_session() as session:
        for item in items:
            product = await session.get(Product, item['product_id'])
            if product:
                product.відкладено = (product.відкладено or 0) + item['quantity']
        await session.commit()

async def orm_clear_all_reservations():
    async with async_session() as session:
        await session.execute(update(Product).values(відкладено=0))
        await session.commit()

# --- НОВІ ФУНКЦІЇ ДЛЯ АРХІВУ ---
async def orm_add_saved_list(user_id: int, file_name: str, file_path: str, items: list):
    """Зберігає інформацію про новий список та його вміст у базу даних."""
    async with async_session() as session:
        new_list = SavedList(user_id=user_id, file_name=file_name, file_path=file_path)
        session.add(new_list)
        await session.flush() # Отримуємо ID для нового списку
        
        for item in items:
            list_item = SavedListItem(
                list_id=new_list.id,
                article_name=item['article_name'],
                quantity=item['quantity']
            )
            session.add(list_item)
        
        await session.commit()

async def orm_get_user_lists_archive(user_id: int):
    """Повертає список збережених файлів для конкретного користувача."""
    async with async_session() as session:
        query = select(SavedList).where(SavedList.user_id == user_id).order_by(SavedList.created_at.desc())
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_all_files_for_user(user_id: int):
    """Повертає шляхи до всіх файлів користувача для ZIP-архівації."""
    async with async_session() as session:
        query = select(SavedList.file_path).where(SavedList.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().all()