import asyncio
import logging
import os
import re
import shutil

import pandas as pd
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload
from thefuzz import fuzz

from config import ARCHIVES_PATH
from database.engine import async_session, sync_session
from database.models import Base, Product, SavedList, SavedListItem, TempList
from lexicon.lexicon import LEXICON


def _extract_article(name_str: str):
    match = re.match(r"^(\d{8,})", name_str)
    return match.group(1) if match else None


def _sync_smart_import(dataframe: pd.DataFrame):
    try:
        df = dataframe
        df.rename(
            columns={"в": "відділ", "г": "група", "н": "назва", "к": "кількість"},
            inplace=True,
        )

        file_articles = set()
        for _, row in df.iterrows():
            if pd.isna(row["назва"]):
                continue
            article = _extract_article(str(row["назва"]))
            if article:
                file_articles.add(article)

        articles_in_file_count = len(file_articles)
        updated_count, added_count, deleted_count = 0, 0, 0

        with sync_session() as session:
            db_products_query = session.execute(select(Product.id, Product.артикул))
            products_to_delete_ids = []
            for prod_id, prod_article in db_products_query:
                if prod_article not in file_articles:
                    products_to_delete_ids.append(prod_id)

            if products_to_delete_ids:
                session.execute(delete(Product).where(Product.id.in_(products_to_delete_ids)))
                deleted_count = len(products_to_delete_ids)

            existing_products_query = session.execute(select(Product))
            existing_products = {
                p.артикул: p for p in existing_products_query.scalars()
            }

            for _, row in df.iterrows():
                if pd.isna(row["назва"]) or pd.isna(row["відділ"]):
                    continue
                full_name = str(row["назва"])
                article = _extract_article(full_name)
                if not article:
                    continue

                if article in existing_products:
                    product = existing_products[article]
                    product.назва = full_name
                    product.відділ = int(row["відділ"])
                    product.група = str(row["група"])
                    product.кількість = str(row["кількість"])
                    updated_count += 1
                else:
                    new_product = Product(
                        артикул=article,
                        назва=full_name,
                        відділ=int(row["відділ"]),
                        група=str(row["група"]),
                        кількість=str(row["кількість"]),
                    )
                    session.add(new_product)
                    added_count += 1

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
        logging.error(f"Error during smart import sync: {e}", exc_info=True)
        return LEXICON.IMPORT_SYNC_ERROR.format(error=str(e))


async def orm_smart_import(dataframe: pd.DataFrame):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_smart_import, dataframe)


async def orm_find_products(search_query: str):
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


async def orm_get_product_by_id(session, product_id: int, for_update: bool = False):
    query = select(Product).where(Product.id == product_id)
    if for_update:
        query = query.with_for_update()
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_update_reserved_quantity(session, items: list):
    for item in items:
        product = await orm_get_product_by_id(
            session, item["product_id"], for_update=True
        )
        if product:
            product.відкладено = (product.відкладено or 0) + item["quantity"]


async def orm_clear_all_reservations():
    async with async_session() as session:
        await session.execute(update(Product).values(відкладено=0))
        await session.commit()


async def orm_add_saved_list(
    user_id: int, file_name: str, file_path: str, items: list, session
):
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


async def orm_get_user_lists_archive(user_id: int):
    async with async_session() as session:
        query = (
            select(SavedList)
            .where(SavedList.user_id == user_id)
            .order_by(SavedList.created_at.desc())
        )
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_all_files_for_user(user_id: int):
    async with async_session() as session:
        query = select(SavedList.file_path).where(SavedList.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_users_with_archives():
    async with async_session() as session:
        query = (
            select(SavedList.user_id, func.count(SavedList.id).label("lists_count"))
            .group_by(SavedList.user_id)
            .order_by(func.count(SavedList.id).desc())
        )
        result = await session.execute(query)
        return result.all()


async def orm_clear_temp_list(user_id: int):
    async with async_session() as session:
        query = delete(TempList).where(TempList.user_id == user_id)
        await session.execute(query)
        await session.commit()


async def orm_add_item_to_temp_list(user_id: int, product_id: int, quantity: int):
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


async def orm_get_temp_list(user_id: int):
    async with async_session() as session:
        query = select(TempList).where(TempList.user_id == user_id).options(selectinload(TempList.product))
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_temp_list_department(user_id: int):
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
    async with async_session() as session:
        query = (
            select(func.sum(TempList.quantity))
            .where(TempList.user_id == user_id, TempList.product_id == product_id)
        )
        result = await session.execute(query)
        quantity = result.scalar_one_or_none()
        return quantity or 0


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


def orm_get_all_collected_items_sync():
    with sync_session() as session:
        all_products_query = select(Product)
        all_products = session.execute(all_products_query).scalars().all()
        products_dict = {p.артикул: p for p in all_products}

        all_saved_items_query = select(SavedListItem)
        all_saved_items = session.execute(all_saved_items_query).scalars().all()

        collected_data = {}
        for item in all_saved_items:
            article = _extract_article(item.article_name)
            if not article or article not in products_dict:
                continue

            product_info = products_dict[article]
            
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


# --- НОВАЯ ФУНКЦИЯ УДАЛЕНИЯ ---
def orm_delete_all_saved_lists_sync():
    """
    Удаляет все сохраненные списки из БД и связанные с ними файлы.
    Возвращает количество удаленных списков.
    """
    with sync_session() as session:
        # 1. Получаем количество списков для отчета
        lists_count = session.execute(select(func.count(SavedList.id))).scalar_one()
        if lists_count == 0:
            return 0
        
        # 2. Удаляем все записи из таблицы saved_lists
        # Благодаря 'cascade="all, delete-orphan"' в models.py, связанные saved_list_items удалятся автоматически
        session.execute(delete(SavedList))
        session.commit()
        
        # 3. Полностью очищаем папку с архивами
        if os.path.exists(ARCHIVES_PATH):
            shutil.rmtree(ARCHIVES_PATH)
        
        return lists_count