# epicservice/database/orm/products.py

import asyncio
import logging
import re

import pandas as pd
from sqlalchemy import delete, func, select, update
from thefuzz import fuzz

from database.engine import async_session, sync_session
from database.models import Product
from lexicon.lexicon import LEXICON

# Налаштовуємо логер для цього модуля
logger = logging.getLogger(__name__)


# --- Допоміжні приватні функції ---

def _extract_article(name_str: str) -> str | None:
    """
    Витягує артикул з початку рядка назви товару.
    """
    if not isinstance(name_str, str):
        name_str = str(name_str)
    match = re.match(r"^(\d{8,})", name_str.strip())
    return match.group(1) if match else None


def _normalize_quantity(value: any) -> str:
    """
    Приводить значення кількості до стандартизованого рядкового типу.
    """
    if value is None:
        return "0"
    s_value = str(value).replace(',', '.').strip()
    s_value = re.sub(r'[^\d.]', '', s_value)
    return s_value if s_value else "0"


# --- Функції імпорту та оновлення даних ---

def _sync_smart_import(dataframe: pd.DataFrame) -> dict:
    """
    Синхронно виконує "розумний" імпорт товарів з DataFrame у базу даних.
    """
    try:
        df = dataframe.rename(
            columns={"в": "відділ", "г": "група", "н": "назва", "к": "кількість"},
            inplace=False,
        )

        file_articles_with_data = {}
        for _, row in df.iterrows():
            if pd.notna(row["назва"]) and (article := _extract_article(row["назва"])):
                file_articles_with_data[article] = int(row.get("відділ", 0))

        file_articles = set(file_articles_with_data.keys())
        updated_count, added_count, deleted_count = 0, 0, 0
        department_stats = {}

        with sync_session() as session:
            db_articles = {p for p in session.execute(select(Product.артикул)).scalars()}

            articles_to_delete = db_articles - file_articles
            if articles_to_delete:
                stmt = delete(Product).where(Product.артикул.in_(articles_to_delete))
                result = session.execute(stmt)
                deleted_count = result.rowcount

            # Отримуємо об'єкти існуючих продуктів, щоб мати доступ до їх ID
            existing_products_query = select(Product)
            existing_products = {p.артикул: p for p in session.execute(existing_products_query).scalars()}

            products_to_update = []
            products_to_add = []

            for _, row in df.iterrows():
                if pd.isna(row["назва"]) or pd.isna(row["відділ"]):
                    continue

                full_name = str(row["назва"]).strip()
                article = _extract_article(full_name)
                if not article:
                    continue

                product_data = {
                    "назва": full_name,
                    "відділ": int(row["відділ"]),
                    "група": str(row["група"]).strip(),
                    "кількість": _normalize_quantity(row["кількість"]),
                }

                if article in existing_products:
                    # ВИПРАВЛЕНО: Додаємо ID існуючого продукту до словника для оновлення
                    product_id = existing_products[article].id
                    update_data = {"id": product_id, "артикул": article, **product_data}
                    products_to_update.append(update_data)
                else:
                    products_to_add.append(Product(артикул=article, **product_data))

            if products_to_update:
                session.bulk_update_mappings(Product, products_to_update)
                updated_count = len(products_to_update)

            if products_to_add:
                session.bulk_save_objects(products_to_add)
                added_count = len(products_to_add)

            session.execute(update(Product).values(відкладено=0))
            session.commit()

            total_in_db = session.execute(select(func.count(Product.id))).scalar_one()

            for art, dep in file_articles_with_data.items():
                department_stats[dep] = department_stats.get(dep, 0) + 1

            return {
                'added': added_count,
                'updated': updated_count,
                'deleted': deleted_count,
                'total_in_db': total_in_db,
                'total_in_file': len(file_articles),
                'department_stats': department_stats
            }

    except Exception as e:
        logger.error(f"Помилка під час синхронного імпорту: {e}", exc_info=True)
        return {}


async def orm_smart_import(dataframe: pd.DataFrame) -> dict:
    """
    Асинхронна обгортка для запуску синхронної функції імпорту.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_smart_import, dataframe)


def _sync_subtract_collected_from_stock(dataframe: pd.DataFrame) -> dict:
    """
    Синхронно віднімає кількість зібраних товарів від залишків у базі.
    """
    processed_count, not_found_count, error_count = 0, 0, 0
    with sync_session() as session:
        for _, row in dataframe.iterrows():
            article = _extract_article(str(row.get("Назва", "")))
            if not article:
                continue
            product = session.execute(select(Product).where(Product.артикул == article)).scalar_one_or_none()
            if not product:
                not_found_count += 1
                logger.warning(f"Віднімання: товар з артикулом {article} не знайдено в БД.")
                continue
            try:
                current_stock = float(str(product.кількість).replace(',', '.'))
                quantity_to_subtract = float(str(row["Кількість"]).replace(',', '.'))
                new_stock = current_stock - quantity_to_subtract
                session.execute(update(Product).where(Product.id == product.id).values(кількість=str(new_stock)))
                processed_count += 1
            except (ValueError, TypeError) as e:
                error_count += 1
                logger.error(f"Помилка конвертації числа для артикула {article}: {e}")
                continue
        session.commit()
    return {'processed': processed_count, 'not_found': not_found_count, 'errors': error_count}


async def orm_subtract_collected(dataframe: pd.DataFrame) -> dict:
    """
    Асинхронна обгортка для запуску синхронної функції віднімання залишків.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_subtract_collected_from_stock, dataframe)


# --- Функції пошуку та отримання товарів ---

async def orm_find_products(search_query: str) -> list[Product]:
    """
    Виконує нечіткий пошук товарів у базі даних.
    """
    async with async_session() as session:
        like_query = f"%{search_query}%"
        stmt = select(Product).where(
            (Product.назва.ilike(like_query)) | (Product.артикул.ilike(like_query))
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()
        if not candidates:
            return []
        scored_products = []
        for product in candidates:
            article_score = fuzz.ratio(search_query, product.артикул) * 1.2
            name_score = fuzz.token_set_ratio(search_query.lower(), product.назва.lower())
            final_score = max(article_score, name_score)
            if final_score > 55:
                scored_products.append((product, final_score))
        scored_products.sort(key=lambda x: x[1], reverse=True)
        return [product for product, score in scored_products[:15]]


async def orm_get_product_by_id(session, product_id: int, for_update: bool = False) -> Product | None:
    """
    Отримує один товар за його унікальним ідентифікатором (ID).
    """
    query = select(Product).where(Product.id == product_id)
    if for_update:
        query = query.with_for_update()
    result = await session.execute(query)
    return result.scalar_one_or_none()


# --- Функції для звітів ---

def orm_get_all_products_sync() -> list[Product]:
    """
    Синхронно отримує всі товари з бази даних для формування звіту.
    """
    with sync_session() as session:
        query = select(Product).order_by(Product.відділ, Product.назва)
        result = session.execute(query)
        return result.scalars().all()