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

    Args:
        name_str: Рядок з повною назвою товару.

    Returns:
        Витягнутий артикул у вигляді рядка або None, якщо артикул не знайдено.
    """
    match = re.match(r"^(\d{8,})", name_str)
    return match.group(1) if match else None


def _sync_smart_import(dataframe: pd.DataFrame) -> str:
    """
    Синхронно виконує "розумний" імпорт товарів з DataFrame у базу даних.
    Оновлює існуючі товари, додає нові та видаляє ті, яких немає у файлі.
    Також обнуляє всі попередні резерви.

    Args:
        dataframe: DataFrame pandas з даними для імпорту.

    Returns:
        Рядок зі звітом про результати імпорту.
    """
    try:
        df = dataframe.rename(
            columns={"в": "відділ", "г": "група", "н": "назва", "к": "кількість"},
            inplace=False,
        )

        file_articles = {
            article
            for _, row in df.iterrows()
            if pd.notna(row["назва"]) and (article := _extract_article(str(row["назва"])))
        }
        articles_in_file_count = len(file_articles)
        updated_count, added_count, deleted_count = 0, 0, 0

        with sync_session() as session:
            # --- ВИПРАВЛЕННЯ ТУТ ---
            # Отримуємо множину всіх артикулів, що є в базі
            db_articles_query = select(Product.артикул)
            db_articles = {p for p in session.execute(db_articles_query).scalars()}
            
            # Видалення продуктів, яких немає у файлі
            articles_to_delete = db_articles - file_articles
            if articles_to_delete:
                stmt = delete(Product).where(Product.артикул.in_(articles_to_delete))
                result = session.execute(stmt)
                deleted_count = result.rowcount

            # Оновлення та додавання продуктів
            existing_products_query = select(Product)
            existing_products = {
                p.артикул: p for p in session.execute(existing_products_query).scalars()
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
            
            # Обнулення всіх резервів
            session.execute(update(Product).values(відкладено=0))
            
            session.commit()

            total_in_db = session.execute(select(func.count(Product.id))).scalar_one()

            # Формування звіту
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
        logging.error(f"Помилка під час синхронного імпорту: {e}", exc_info=True)
        return LEXICON.IMPORT_SYNC_ERROR.format(error=str(e))


async def orm_smart_import(dataframe: pd.DataFrame) -> str:
    """
    Асинхронна обгортка для запуску синхронної функції імпорту в окремому потоці.

    Args:
        dataframe: DataFrame pandas з даними для імпорту.

    Returns:
        Рядок зі звітом про результати імпорту.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_smart_import, dataframe)


async def orm_find_products(search_query: str) -> list[Product]:
    """
    Виконує нечіткий пошук товарів у базі даних за назвою або артикулом.

    Args:
        search_query: Рядок для пошуку.

    Returns:
        Список знайдених об'єктів Product, відсортований за релевантністю.
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

            if final_score > 55:  # Поріг релевантності
                scored_products.append((product, final_score))

        scored_products.sort(key=lambda x: x[1], reverse=True)
        return [product for product, score in scored_products[:15]] # Обмеження кількості результатів


async def orm_get_product_by_id(session, product_id: int, for_update: bool = False) -> Product | None:
    """
    Отримує один товар за його унікальним ідентифікатором (ID).

    Args:
        session: Асинхронна сесія SQLAlchemy.
        product_id: ID товару.
        for_update: Чи потрібно блокувати рядок для оновлення (песимістичне блокування).

    Returns:
        Об'єкт Product або None, якщо товар не знайдено.
    """
    query = select(Product).where(Product.id == product_id)
    if for_update:
        query = query.with_for_update()
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_update_reserved_quantity(session, items: list[dict]):
    """
    Оновлює кількість зарезервованих товарів.

    Args:
        session: Асинхронна сесія SQLAlchemy.
        items: Список словників, кожен з яких містить 'product_id' та 'quantity'.
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

    Args:
        user_id: Telegram ID користувача.
        file_name: Назва згенерованого Excel-файлу.
        file_path: Шлях до згенерованого Excel-файлу.
        items: Список товарів для збереження.
        session: Асинхронна сесія SQLAlchemy.
    """
    new_list = SavedList(user_id=user_id, file_name=file_name, file_path=file_path)
    session.add(new_list)
    await session.flush()  # Отримуємо ID для new_list
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

    Args:
        user_id: Telegram ID користувача.

    Returns:
        Список об'єктів SavedList.
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

    Args:
        user_id: Telegram ID користувача.

    Returns:
        Список шляхів до файлів.
    """
    async with async_session() as session:
        query = select(SavedList.file_path).where(SavedList.user_id == user_id)
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_users_with_archives() -> list[tuple[int, int]]:
    """
    Отримує список користувачів, які мають хоча б один збережений список,
    та кількість їхніх списків.

    Returns:
        Список кортежів (user_id, lists_count).
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

    Args:
        user_id: Telegram ID користувача.
    """
    async with async_session() as session:
        query = delete(TempList).where(TempList.user_id == user_id)
        await session.execute(query)
        await session.commit()


async def orm_add_item_to_temp_list(user_id: int, product_id: int, quantity: int):
    """
    Додає товар до тимчасового списку користувача.
    Якщо товар вже є у списку, оновлює його кількість.

    Args:
        user_id: Telegram ID користувача.
        product_id: ID товару.
        quantity: Кількість товару.
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
    Отримує поточний тимчасовий список користувача з повною інформацією про товари.

    Args:
        user_id: Telegram ID користувача.

    Returns:
        Список об'єктів TempList.
    """
    async with async_session() as session:
        query = select(TempList).where(TempList.user_id == user_id).options(selectinload(TempList.product))
        result = await session.execute(query)
        return result.scalars().all()


async def orm_get_temp_list_department(user_id: int) -> int | None:
    """
    Визначає відділ поточного тимчасового списку користувача (за першим товаром).

    Args:
        user_id: Telegram ID користувача.

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
        result = await session.execute(query)
        first_item = result.scalar_one_or_none()
        return first_item.product.відділ if first_item and first_item.product else None


async def orm_get_temp_list_item_quantity(user_id: int, product_id: int) -> int:
    """
    Отримує кількість конкретного товару в тимчасовому списку користувача.

    Args:
        user_id: Telegram ID користувача.
        product_id: ID товару.

    Returns:
        Кількість товару (0, якщо товару немає у списку).
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

    Returns:
        Список словників з агрегованими даними по кожному товару.
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

    Returns:
        Кількість видалених списків.
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
    Синхронно знаходить користувачів, яким потрібно надіслати попередження
    про майбутнє видалення їхніх старих списків.

    Args:
        hours_warn: Мінімальний вік списку для попередження (у годинах).
        hours_expire: Максимальний вік списку для попередження (у годинах).

    Returns:
        Множина унікальних ID користувачів.
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
    Синхронно видаляє списки (разом із файлами), які старші за вказану кількість годин.

    Args:
        hours: Максимально дозволений вік списку в годинах.

    Returns:
        Кількість видалених списків.
    """
    with sync_session() as session:
        expire_time = datetime.now() - timedelta(hours=hours)
        
        query = select(SavedList).where(SavedList.created_at < expire_time)
        lists_to_delete = session.execute(query).scalars().all()
        
        if not lists_to_delete:
            return 0
            
        count = len(lists_to_delete)
        list_ids_to_delete = [lst.id for lst in lists_to_delete]
        
        # Видалення файлів
        for lst in lists_to_delete:
            if os.path.exists(lst.file_path):
                try:
                    user_dir = os.path.dirname(lst.file_path)
                    os.remove(lst.file_path)
                    if not os.listdir(user_dir): # Видаляємо папку користувача, якщо вона порожня
                        os.rmdir(user_dir)
                except OSError as e:
                    logging.error(f"Помилка видалення архівного файлу або папки {lst.file_path}: {e}")

        # Видалення з БД
        session.execute(delete(SavedListItem).where(SavedListItem.list_id.in_(list_ids_to_delete)))
        session.execute(delete(SavedList).where(SavedList.id.in_(list_ids_to_delete)))
        
        session.commit()
        return count