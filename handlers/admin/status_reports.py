# epicservice/handlers/admin/status_reports.py

import asyncio
import logging
from typing import Dict

from aiogram import F, Router
from aiogram.types import CallbackQuery

from config import ADMIN_IDS
from database.orm import (orm_get_collection_status_sync,
                          orm_get_stock_status_sync)
from lexicon.lexicon import LEXICON

# Налаштовуємо логер
logger = logging.getLogger(__name__)

# Створюємо роутер
router = Router()
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


def format_report(title: str, data: Dict[int, int]) -> str:
    """
    Універсальна функція для форматування текстових звітів.
    """
    if not data:
        return LEXICON.REPORT_EMPTY_DATA

    report_lines = [title]
    # Сортуємо відділи для послідовного виводу
    sorted_departments = sorted(data.items())

    for dep_id, count in sorted_departments:
        report_lines.append(LEXICON.REPORT_DEPARTMENT_ITEM.format(dep_id=dep_id, count=count))

    return "\n".join(report_lines)


@router.callback_query(F.data == "admin:stock_status")
async def get_stock_status_handler(callback: CallbackQuery):
    """
    Обробляє запит на звіт "Стан складу".
    """
    await callback.answer("Формую звіт про стан складу...")

    loop = asyncio.get_running_loop()
    # Виконуємо синхронну функцію в окремому потоці
    report_data = await loop.run_in_executor(None, orm_get_stock_status_sync)

    report_text = format_report(LEXICON.STOCK_STATUS_REPORT_TITLE, report_data)

    await callback.message.answer(report_text)


@router.callback_query(F.data == "admin:collection_status")
async def get_collection_status_handler(callback: CallbackQuery):
    """
    Обробляє запит на звіт "Стан збору".
    """
    await callback.answer("Формую звіт про стан збору...")

    loop = asyncio.get_running_loop()
    # Виконуємо синхронну функцію в окремому потоці
    report_data = await loop.run_in_executor(None, orm_get_collection_status_sync)

    report_text = format_report(LEXICON.COLLECTION_STATUS_REPORT_TITLE, report_data)

    await callback.message.answer(report_text)