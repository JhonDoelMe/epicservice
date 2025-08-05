import asyncio
import pandas as pd
import re
from sqlalchemy import delete, select, update, func

from database.engine import async_engine, sync_session, async_session
from database.models import Base, Product, SavedList, SavedListItem

async def create_tables():
    """Створює всі таблиці в базі даних."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def _extract_article(name_str: str):
    """Витягує перші 8+ цифр з початку рядка."""
    match = re.match(r'^(\d{8,})', name_str)
    return match.group(1) if match else None

def _sync_smart_import(file_path: str):
    """Виконує "розумний імпорт" (UPSERT)."""
    try:
        df = pd.read_excel(file_path)
        expected_columns = ['в', 'г', 'н', 'к']
        if list(df.columns) != expected_columns:
            return f"❌ Помилка: назви колонок неправильні. Очікується: `в, г, н, к`"

        df.rename(columns={'в': 'відділ', 'г': 'група', 'н': 'назва', 'к': 'кількість'}, inplace=True)
        updated_count, added_count = 0, 0

        with sync_session() as session:
            existing_products_query = session.execute(select(Product))
            existing_products = {p.артикул: p for p in existing_products_query.scalars()}

            for _, row in df.iterrows():
                if pd.isna(row['назва']) or pd.isna(row['відділ']): continue
                full_name = str(row['назва'])
                article = _extract_article(full_name)
                if not article: continue

                if article in existing_products:
                    product = existing_products[article]
                    product.назва = full_name
                    product.відділ = int(row['відділ'])
                    product.група = str(row['група'])
                    product.кількість = str(row['кількість'])
                    updated_count += 1
                else:
                    new_product = Product(артикул=article, назва=full_name, відділ=int(row['відділ']), група=str(row['група']), кількість=str(row['кількість']))
                    session.add(new_product)
                    added_count += 1
            session.commit()
        
        return f"✅ Імпорт завершено!\n🔄 Оновлено товарів: {updated_count}\n➕ Додано нових: {added_count}"

    except Exception as e:
        return f"❌ Сталася помилка: {str(e)}"

async def orm_smart_import(file_path: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_smart_import, file_path)

async def orm_find_products(search_query: str):
    async with async_session() as session:
        query = select(Product).where((Product.назва.ilike(f'%{search_query}%')) | (Product.артикул.ilike(f'%{search_query}%'))).limit(15)
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_product_by_id(product_id: int):
    async with async_session() as session:
        return await session.get(Product, product_id)

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

async def orm_add_saved_list(user_id: int, file_name: str, file_path: str, items: list):
    async with async_session() as session:
        new_list = SavedList(user_id=user_id, file_name=file_name, file_path=file_path)
        session.add(new_list)
        await session.flush()
        for item in items:
            list_item = SavedListItem(list_id=new_list.id, article_name=item['article_name'], quantity=item['quantity'])
            session.add(list_item)
        await session.commit()

async def orm_get_user_lists_archive(user_id: int):
    async with async_session() as session:
        query = select(SavedList).where(SavedList.user_id == user_id).order_by(SavedList.created_at.desc())
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_all_files_for_user(user_id: int):
    async with async_session() as session:
        query = select(SavedList.file_path).where(SavedList.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_users_with_archives():
    async with async_session() as session:
        query = select(SavedList.user_id, func.count(SavedList.id).label('lists_count')).group_by(SavedList.user_id).order_by(func.count(SavedList.id).desc())
        result = await session.execute(query)
        return result.all()