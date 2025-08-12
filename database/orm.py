import asyncio
import pandas as pd
import re
from sqlalchemy import delete, select, update, func, bindparam
from sqlalchemy.orm import selectinload
from thefuzz import fuzz

from database.engine import async_engine, sync_session, async_session
from database.models import Base, Product, SavedList, SavedListItem, TempList

async def create_tables():
    """Створює всі таблиці в базі даних."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- Функції імпорту ---
def _extract_article(name_str: str):
    match = re.match(r'^(\d{8,})', name_str)
    return match.group(1) if match else None

def _sync_smart_import(file_path: str):
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

# --- ВИПРАВЛЕНА ФУНКЦІЯ ПОШУКУ ---
async def orm_find_products(search_query: str):
    """
    Виконує комбінований пошук: спочатку швидкий SQL LIKE,
    потім сортування результатів за допомогою нечіткого порівняння.
    """
    async with async_session() as session:
        # 1. Швидкий відбір кандидатів за допомогою ILIKE
        # Шукаємо як по назві, так і по артикулу
        like_query = f"%{search_query}%"
        stmt = select(Product).where(
            (Product.назва.ilike(like_query)) | (Product.артикул.ilike(like_query))
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        if not candidates:
            return []

        # 2. Розрахунок релевантності та сортування
        # fuzz.token_set_ratio добре працює з частковими збігами та різним порядком слів
        scored_products = []
        for product in candidates:
            # Надаємо пріоритет збігам по артикулу
            article_score = fuzz.ratio(search_query, product.артикул) * 1.2 # Множник для пріоритету
            name_score = fuzz.token_set_ratio(search_query.lower(), product.назва.lower())
            
            # Використовуємо вищий з двох показників
            final_score = max(article_score, name_score)

            if final_score > 55: # Поріг схожості
                scored_products.append((product, final_score))

        # Сортуємо за спаданням релевантності
        scored_products.sort(key=lambda x: x[1], reverse=True)

        # Повертаємо топ-15 результатів
        return [product for product, score in scored_products[:15]]


async def orm_get_product_by_id(session, product_id: int, for_update: bool = False):
    """
    Знаходить один товар за його ID.
    Якщо for_update=True, блокує рядок для оновлення.
    """
    query = select(Product).where(Product.id == product_id)
    if for_update:
        query = query.with_for_update()
    result = await session.execute(query)
    return result.scalar_one_or_none()

# --- Функції резервування ---
async def orm_update_reserved_quantity(session, items: list):
    """Оновлює поле 'відкладено', використовуючи існуючу сесію."""
    for item in items:
        # Блокуємо рядок товару перед оновленням
        product = await orm_get_product_by_id(session, item['product_id'], for_update=True)
        if product:
            product.відкладено = (product.відкладено or 0) + item['quantity']

async def orm_clear_all_reservations():
    async with async_session() as session:
        await session.execute(update(Product).values(відкладено=0))
        await session.commit()

# --- Функції архіву ---
async def orm_add_saved_list(user_id: int, file_name: str, file_path: str, items: list, session):
    new_list = SavedList(user_id=user_id, file_name=file_name, file_path=file_path)
    session.add(new_list)
    await session.flush()
    for item in items:
        list_item = SavedListItem(list_id=new_list.id, article_name=item['article_name'], quantity=item['quantity'])
        session.add(list_item)

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

# --- Функції тимчасових списків ("кошиків") ---
async def orm_clear_temp_list(user_id: int):
    async with async_session() as session:
        query = delete(TempList).where(TempList.user_id == user_id)
        await session.execute(query)
        await session.commit()

async def orm_add_item_to_temp_list(user_id: int, product_id: int, quantity: int):
    async with async_session() as session:
        new_item = TempList(user_id=user_id, product_id=product_id, quantity=quantity)
        session.add(new_item)
        await session.commit()

async def orm_get_temp_list(user_id: int):
    async with async_session() as session:
        query = select(TempList).where(TempList.user_id == user_id).options(selectinload(TempList.product))
        result = await session.execute(query)
        return result.scalars().all()

async def orm_get_temp_list_department(user_id: int):
    async with async_session() as session:
        query = select(TempList).where(TempList.user_id == user_id).options(selectinload(TempList.product)).limit(1)
        result = await session.execute(query)
        first_item = result.scalar_one_or_none()
        return first_item.product.відділ if first_item and first_item.product else None

# --- Синхронні функції для експорту ---
def orm_get_all_products_sync():
    with sync_session() as session:
        query = select(Product).order_by(Product.відділ, Product.назва)
        result = session.execute(query)
        return result.scalars().all()

def orm_get_all_temp_list_items_sync():
    with sync_session() as session:
        query = select(TempList)
        result = session.execute(query)
        return result.scalars().all()