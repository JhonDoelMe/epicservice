import asyncio
import logging
import os
import pandas as pd
import json
import base64

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    WebAppInfo, # <-- Важный импорт для Mini App
)
from dotenv import load_dotenv

# --- Конфигурация ---
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
logging.basicConfig(level=logging.INFO)

# --- Инициализация ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# Структура для хранения списков
user_lists = {}


# --- Машина состояний (FSM) ---
class Form(StatesGroup):
    waiting_for_quantity = State()


# --- Клавиатуры ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Новий список"), KeyboardButton(text="Мій список")]],
    resize_keyboard=True,
)


# --- Логика поиска в Google Sheets ---
def find_product_by_article(article_number: str) -> dict | None:
    if not GOOGLE_SHEET_URL:
        logging.error("Переменная GOOGLE_SHEET_URL не задана в .env файле.")
        return None
    try:
        # Указываем запятую как разделитель
        df = pd.read_csv(GOOGLE_SHEET_URL, delimiter=',')
        df['артикул'] = df['артикул'].astype(str)
        result_row = df[df['артикул'] == article_number]
        if not result_row.empty:
            return result_row.iloc[0].to_dict()
    except Exception as e:
        logging.error(f"Ошибка при чтении данных из Google Sheets: {e}")
        return None
    return None


# --- Основные команды ---

@dp.message(CommandStart())
async def send_welcome(message: Message):
    await message.answer(
        "👋 *Вітаю!*\n\n"
        "Я бот для пошуку товарів та створення списків.\n"
        "Використовуйте кнопки нижче або просто надішліть мені артикул.",
        reply_markup=main_keyboard,
    )


# --- Работа со списками ---

@dp.message(F.text == "Новий список")
async def new_list_handler(message: Message):
    user_id = message.from_user.id
    user_lists[user_id] = {"list": [], "first_article": None, "allowed_department": None}
    await message.answer(
        "Створено новий порожній список. Тепер шукайте товари та додавайте їх."
    )


@dp.message(F.text == "Мій список")
async def my_list_handler(message: Message):
    """Показывает кнопку для открытия Mini App со списком."""
    user_id = message.from_user.id
    if user_id not in user_lists or not user_lists[user_id]["list"]:
        await message.answer("Ваш список порожній. Спочатку створіть новий список і додайте товари.")
        return

    # Готовим данные для передачи в Mini App
    list_data = user_lists[user_id]["list"]
    # Превращаем данные в JSON, затем в байты, затем в безопасную для URL строку Base64
    list_data_b64 = base64.urlsafe_b64encode(json.dumps(list_data).encode()).decode()

    # Формируем URL с вашим доменом и параметром
    web_app_url = f"https://anubis-ua.pp.ua/?start_param={list_data_b64}"

    # Создаем кнопку, которая открывает веб-приложение
    web_app_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Відкрити мій список", web_app=WebAppInfo(url=web_app_url))]
    ])

    await message.answer(
        f"У вашому списку *{len(list_data)}* позицій. Натисніть кнопку нижче, щоб переглянути.",
        reply_markup=web_app_keyboard
    )


@dp.callback_query(F.data == "save_list")
async def save_list_callback_handler(callback_query: types.CallbackQuery):
    """Сохраняет список в Excel и отправляет пользователю."""
    user_id = callback_query.from_user.id
    if user_id not in user_lists or not user_lists[user_id]["list"]:
        await callback_query.message.answer("Список порожній, нічого зберігати.")
        await callback_query.answer()
        return

    user_data = user_lists[user_id]
    df_list = pd.DataFrame(user_data["list"])
    file_name = f"{str(user_data['first_article'])[:4]}.xlsx"

    try:
        df_list.to_excel(file_name, index=False, header=False)
        document = FSInputFile(file_name)
        await callback_query.message.answer_document(
            document, caption=f"Ваш список збережено у файлі: *{file_name}*"
        )
        del user_lists[user_id]
    except Exception as e:
        logging.error(f"Ошибка сохранения файла: {e}")
        await callback_query.message.answer("Сталася помилка при збереженні файлу.")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)
    await callback_query.answer("Список збережено!")


# --- Поиск и добавление в список ---

@dp.callback_query(F.data.startswith("add_to_list_"))
async def add_to_list_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Ловит нажатие кнопки, проверяет отдел и переходит в состояние ожидания количества."""
    user_id = callback_query.from_user.id
    article_to_add = callback_query.data.split("_")[-1]
    product_data = find_product_by_article(article_to_add)

    if not product_data:
        await callback_query.answer("Помилка: товар не знайдено.", show_alert=True)
        return

    if user_id in user_lists:
        allowed_department = user_lists[user_id].get("allowed_department")
        if allowed_department is not None and product_data.get("відділ") != allowed_department:
            await callback_query.answer(
                f"Заборонено! Усі товари повинні бути з відділу {allowed_department}.",
                show_alert=True
            )
            return

    await state.update_data(article_to_add=article_to_add)
    await state.set_state(Form.waiting_for_quantity)
    await callback_query.message.answer(
        f"Введіть кількість для товару з артикулом `{article_to_add}`:"
    )
    await callback_query.answer()


@dp.message(StateFilter(Form.waiting_for_quantity), F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    """Получает количество, добавляет товар и запоминает отдел, если это первый товар."""
    user_id = message.from_user.id
    quantity = int(message.text)
    data = await state.get_data()
    article = data.get("article_to_add")

    if not article:
        await message.answer("Сталася помилка. Спробуйте додати товар знову.")
        await state.clear()
        return

    if user_id not in user_lists:
        user_lists[user_id] = {"list": [], "first_article": None, "allowed_department": None}

    if not user_lists[user_id]["list"]:
        product_data = find_product_by_article(article)
        if product_data:
            user_lists[user_id]["allowed_department"] = product_data.get("відділ")
        user_lists[user_id]["first_article"] = article

    user_lists[user_id]["list"].append({"артикул": article, "кількість": quantity})
    await message.answer(
        f"✅ Товар з артикулом `{article}` у кількості *{quantity}* додано до вашого списку."
    )
    await state.clear()


@dp.message(F.text.isdigit())
async def search_article_handler(message: Message):
    """Ищет артикул и предлагает добавить в список."""
    product_data = find_product_by_article(message.text)
    if product_data:
        response_text = (
            f"✅ *Знайдено товар*\n\n"
            f"🏢 *Відділ:* {product_data.get('відділ', 'не вказано')}\n"
            f"📂 *Група:* {product_data.get('група', 'не вказано')}\n"
            f"📝 *Назва:* {product_data.get('назва', 'не вказано')}\n"
            f"📦 *Кількість на складі:* {product_data.get('кількість', 'не вказано')}"
        )
        add_button = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🛒 Додати в список", callback_data=f"add_to_list_{product_data.get('артикул')}")]]
        )
        await message.answer(response_text, reply_markup=add_button)
    else:
        await message.answer(f"❌ *Товар з артикулом `{message.text}` не знайдено*")


# --- Точка входа ---
async def main():
    logging.info("Бот запускається...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())