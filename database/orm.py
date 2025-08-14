import asyncio
import logging
import os
import re
import shutil
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload
from thefuzz import fuzz

from config import ARCHIVES_PATH
from database.engine import async_session, sync_session
from database.models import Base, Product, SavedList, SavedListItem, TempList
from lexicon.lexicon import LEXICON

logger = logging.getLogger(__name__)


def _extract_article(name_str: str) -> str | None:
    """
    Витягує артикул з початку рядка назви товару.
    Артикул повинен складатися з 8 або більше цифр.
    """
    if not isinstance(name_str, str):
        name_str = str(name_str)
    match = re.match(r"^(\d{8,})", name_str.strip())
    return match.group(1) if match else None

def _normalize_quantity(value: any) -> str:
    """
    Приводить значення кількості до чистого рядкового типу.
    """
    if value is None:
        return "0"
    s_value = str(value).replace(',', '.').strip()
    s_value = re.sub(r'[^\d.]', '', s_value)
    return s_value if s_value else "0"


def _sync_smart_import(dataframe: pd.DataFrame) -> str:
    """
    Синхронно виконує "розумний" імпорт товарів з DataFrame у базу даних.
    """
    try:
        df = dataframe.rename(
            columns={"в": "відділ", "г": "група", "н": "назва", "к": "кількість"},
            inplace=False,
        )

        file_articles = {
            article
            for _, row in df.iterrows()
            if pd.notna(row["назва"]) and (article := _extract_article(row["назва"]))
        }
        articles_in_file_count = len(file_articles)
        updated_count, added_count, deleted_count = 0, 0, 0

        with sync_session() as session:
            db_articles_query = select(Product.артикул)
            db_articles = {p for p in session.execute(db_articles_query).scalars()}
            
            articles_to_delete = db_articles - file_articles
            if articles_to_delete:
                stmt = delete(Product).where(Product.артикул.in_(articles_to_delete))
                result = session.execute(stmt)
                deleted_count = result.rowcount

            existing_products_query = select(Product)
            existing_products = {
                p.артикул: p for p in session.execute(existing_products_query).scalars()
            }

            for _, row in df.iterrows():
                if pd.isna(row["назва"]) or pd.isna(row["відділ"]):
                    continue
                
                full_name = str(row["назва"]).strip()
                quantity_normalized = _normalize_quantity(row["кількість"])
                
                article = _extract_article(full_name)
                if not article:
                    continue

                product_data = {
                    "назва": full_name,
                    "відділ": int(row["відділ"]),
                    "група": str(row["група"]).strip(),
                    "кількість": quantity_normalized,
                }

                if article in existing_products:
                    stmt = update(Product).where(Product.артикул == article).values(**product_data)
                    session.execute(stmt)
                    updated_count += 1
                else:
                    new_product = Product(артикул=article, **product_data)
                    session.add(new_product)
                    added_count += 1
            
            session.execute(update(Product).values(відкладено=0))
            session.commit()

            total_in_db = session.execute(select(func.count(Product.id))).scalar_one()

            report_lines = [
                LEXICON.IMPORT_REPORT_TITLE,
                LEXICON.IMPORT_REPORT_ADDED.format(added=added_count),
                LEXICON.IMPORT_REPORT_UPDATED.format(updated=updated_count),
                LEXICON.IMPORT_REPORT_DELETED.format(deleted=deleted_count),
                LEXICON.IMPORT_REPORT_TOTAL.format(total=total_in_db),
            ]
            if total_in_db == articles_in_file_count:
                report_lines.append(LEXICON.IMPORT_REPORT_SUCCESS_CHECK.format(count=articles_in_file_count))
            else:
                report_lines.append(LEXICON.IMPORT_REPORT_FAIL_CHECK.format(db_count=total_in_db, file_count=articles_in_file_count))

            return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"Помилка під час синхронного імпорту: {e}", exc_info=True)
        return LEXICON.IMPORT_SYNC_ERROR.format(error=str(e))


async def orm_smart_import(dataframe: pd.DataFrame) -> str:
    """
    Асинхронна обгортка для запуску синхронної функції імпорту.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_smart_import, dataframe)


def _sync_subtract_collected_from_stock(dataframe: pd.DataFrame) -> str:
    """
    Синхронно віднімає кількість зібраних товарів (з звіту) від залишків у базі.
    """
    processed_count = 0
    not_found_count = 0
    error_count = 0
    
    with sync_session() as session:
        for _, row in dataframe.iterrows():
            article = _extract_article(str(row.get("Назва", "")))
            if not article:
                continue

            product_stmt = select(Product).where(Product.артикул == article)
            product = session.execute(product_stmt).scalar_one_or_none()

            if not product:
                not_found_count += 1
                logger.warning(f"Віднімання: товар з артикулом {article} не знайдено в БД.")
                continue

            try:
                current_stock = float(str(product.кількість).replace(',', '.'))
                quantity_to_subtract = float(str(row["Кількість"]).replace(',', '.'))
                
                new_stock = current_stock - quantity_to_subtract
                
                update_stmt = update(Product).where(Product.id == product.id).values(кількість=str(new_stock))
                session.execute(update_stmt)
                
                processed_count += 1

            except (ValueError, TypeError) as e:
                error_count += 1
                logger.error(f"Помилка конвертації числа для артикула {article}: {e}")
                continue
        
        session.commit()

    report_lines = [
        LEXICON.SUBTRACT_REPORT_TITLE,
        LEXICON.SUBTRACT_REPORT_PROCESSED.format(processed=processed_count),
        LEXICON.SUBTRACT_REPORT_NOT_FOUND.format(not_found=not_found_count),
        LEXICON.SUBTRACT_REPORT_ERROR.format(errors=error_count),
    ]
    return "\n".join(report_lines)


async def orm_subtract_collected(dataframe: pd.DataFrame) -> str:
    """
    Асинхронна обгортка для запуску синхронної функції віднімання залишків.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_subtract_collected_from_stock, dataframe)


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


async def orm_update_reserved_quantity(session, items: list[dict]):
    """
    Оновлює кількість зарезервованих товарів.
    """
    for item in items:
        product = await orm_get_product_by_id(
            session, item["product_id"], for_update=True
        )
        if product:
            product.відкладено = (product.відкладено or 0) + item["quantity"]


async def orm_add_saved_list(user_id: int, file_name: str, file_path: str, items: list[dict], session):
    """
    Додає інформацію про новий збережений список до бази даних.
    """
    new_list = SavedList(user_id=user_id, file_name=file_name, file_path=file_path)
    session.add(new_list)
    await session.flush()
    for item in items:
        list_item = SavedListItem(
            list_id=new_list.id,
            article_name=item["article_name"],
            quantity=item["quantity"],
        )
        session.add(list_item)


async def orm_get_user_lists_archive(user_id: int) -> list[SavedList]:
    """
    Отримує архів збережених списків для конкретного користувача.
    """
    async with async_session() as session:
        query = (
            select(SavedList)
            .where(SavedList.user_id == user_id)
            .order_by(SavedList.created_at.desc())
        )
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_all_files_for_user(user_id: int) -> list[str]:
    """
    Отримує шляхи до всіх збережених файлів-списків для користувача.
    """
    async with async_session() as session:
        query = select(SavedList.file_path).where(SavedList.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_users_with_archives() -> list[tuple[int, int]]:
    """
    Отримує список користувачів, які мають хоча б один збережений список.
    """
    async with async_session() as session:
        query = (
            select(SavedList.user_id, func.count(SavedList.id).label("lists_count"))
            .group_by(SavedList.user_id)
            .order_by(func.count(SavedList.id).desc())
        )
        result = await session.execute(query)
        return result.all()


async def orm_clear_temp_list(user_id: int):
    """
    Повністю очищує тимчасовий список для користувача.
    """
    async with async_session() as session:
        query = delete(TempList).where(TempList.user_id == user_id)
        await session.execute(query)
        await session.commit()


async def orm_add_item_to_temp_list(user_id: int, product_id: int, quantity: int):
    """
    Додає товар до тимчасового списку користувача.
    """
    async with async_session() as session:
        query = select(TempList).where(
            TempList.user_id == user_id, TempList.product_id == product_id
        )
        result = await session.execute(query)
        existing_item = result.scalar_one_or_none()

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
    Отримує поточний тимчасовий список користувача.
    """
    async with async_session() as session:
        query = select(TempList).where(TempList.user_id == user_id).options(selectinload(TempList.product))
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_temp_list_department(user_id: int) -> int | None:
    """
    Визначає відділ поточного тимчасового списку користувача.
    """
    async with async_session() as session:
        query = (
            select(TempList)
            .where(TempList.user_id == user_id)
            .options(selectinload(TempList.product))
            .limit(1)
        )
        result = await session.execute(query)
        first_item = result.scalar_one_or_none()
        return first_item.product.відділ if first_item and first_item.product else None


async def orm_get_temp_list_item_quantity(user_id: int, product_id: int) -> int:
    """
    Отримує кількість конкретного товару в тимчасовому списку користувача.
    """
    async with async_session() as session:
        query = (
            select(func.sum(TempList.quantity))
            .where(TempList.user_id == user_id, TempList.product_id == product_id)
        )
        result = await session.execute(query)
        quantity = result.scalar_one_or_none()
        return quantity or 0

# --- Синхронні функції для звітів та фонових завдань ---

def orm_get_all_products_sync() -> list[Product]:
    """Синхронно отримує всі товари з бази даних."""
    with sync_session() as session:
        query = select(Product).order_by(Product.відділ, Product.назва)
        result = session.execute(query)
        return result.scalars().all()


def orm_get_all_temp_list_items_sync() -> list[TempList]:
    """Синхронно отримує всі позиції з усіх тимчасових списків."""
    with sync_session() as session:
        query = select(TempList)
        result = session.execute(query)
        return result.scalars().all()


def orm_get_all_collected_items_sync() -> list[dict]:
    """
    Синхронно збирає зведені дані про всі товари у всіх збережених списках.
    """
    with sync_session() as session:
        all_products_query = select(Product)
        all_products = {p.артикул: p for p in session.execute(all_products_query).scalars()}
        
        all_saved_items_query = select(SavedListItem)
        all_saved_items = session.execute(all_saved_items_query).scalars().all()

        collected_data = {}
        for item in all_saved_items:
            article = _extract_article(item.article_name)
            if not article or article not in all_products:
                continue

            product_info = all_products[article]
            
            if article in collected_data:
                collected_data[article]["quantity"] += item.quantity
            else:
                collected_data[article] = {
                    "department": product_info.відділ,
                    "group": product_info.група,
                    "name": product_info.назва,
                    "quantity": item.quantity,
                }
        
        return list(collected_data.values())


def orm_delete_all_saved_lists_sync() -> int:
    """
    Синхронно видаляє абсолютно всі збережені списки, їхні позиції та файли.
    """
    with sync_session() as session:
        lists_count_query = select(func.count(SavedList.id))
        lists_count = session.execute(lists_count_query).scalar_one()
        if lists_count == 0:
            return 0
        
        session.execute(delete(SavedListItem))
        session.execute(delete(SavedList))
        session.commit()
        
        if os.path.exists(ARCHIVES_PATH):
            shutil.rmtree(ARCHIVES_PATH)
        
        return lists_count


def orm_get_users_for_warning_sync(hours_warn: int, hours_expire: int) -> set[int]:
    """
    Синхронно знаходить користувачів для попередження про видалення списків.
    """
    with sync_session() as session:
        warn_time = datetime.now() - timedelta(hours=hours_warn)
        expire_time = datetime.now() - timedelta(hours=hours_expire)

        query = (
            select(SavedList.user_id)
            .where(SavedList.created_at < warn_time, SavedList.created_at > expire_time)
            .distinct()
        )
        result = session.execute(query).scalars().all()
        return set(result)


def orm_delete_lists_older_than_sync(hours: int) -> int:
    """
    Синхронно видаляє списки, які старші за вказану кількість годин.
    """
    with sync_session() as session:
        expire_time = datetime.now() - timedelta(hours=hours)
        
        query = select(SavedList).where(SavedList.created_at < expire_time)
        lists_to_delete = session.execute(query).scalars().all()
        
        if not lists_to_delete:
            return 0
            
        count = len(lists_to_delete)
        list_ids_to_delete = [lst.id for lst in lists_to_delete]
        
        for lst in lists_to_delete:
            if os.path.exists(lst.file_path):
                try:
                    user_dir = os.path.dirname(lst.file_path)
                    os.remove(lst.file_path)
                    if not os.listdir(user_dir):
                        os.rmdir(user_dir)
                except OSError as e:
                    logging.error(f"Помилка видалення архівного файлу або папки {lst.file_path}: {e}")

        session.execute(delete(SavedListItem).where(SavedListItem.list_id.in_(list_ids_to_delete)))
        session.execute(delete(SavedList).where(SavedList.id.in_(list_ids_to_delete)))
        
        session.commit()
        return count