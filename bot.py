import asyncio
import logging
import os
import pandas as pd

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
)
from dotenv import load_dotenv

# --- Конфигурация ---
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Читаем URL из .env файла
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
logging.basicConfig(level=logging.INFO)

# --- Инициализация ---
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# Словарь для хранения временных списков пользователей
user_lists = {}


# --- Машина состояний (FSM) для ожидания количества ---
class Form(StatesGroup):
    waiting_for_quantity = State()


# --- Клавиатуры ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Новий список"), KeyboardButton(text="Мій список")]],
    resize_keyboard=True,
)


# --- Логика поиска в Google Sheets по ссылке ---
def find_product_by_article(article_number: str) -> dict | None:
    """Ищет товар по артикулу в опубликованной Google Таблице."""
    if not GOOGLE_SHEET_URL:
        logging.error("Переменная GOOGLE_SHEET_URL не задана в .env файле.")
        return None
    try:
        # Читаем данные напрямую из Google Sheets по ссылке, указывая разделитель
        df = pd.read_csv(GOOGLE_SHEET_URL, delimiter=',')
        
        df['артикул'] = df['артикул'].astype(str)
        result_row = df[df['артикул'] == article_number]
        if not result_row.empty:
            return result_row.iloc[0].to_dict()
            
    except Exception as e:
        logging.error(f"Ошибка при чтении данных из Google Sheets: {e}")
        return None
    return None


# --- Обработчики основных команд ---

@dp.message(CommandStart())
async def send_welcome(message: Message):
    """Отправляет приветствие и главную клавиатуру."""
    await message.answer(
        "👋 *Вітаю!*\n\n"
        "Я бот для пошуку товарів та створення списків.\n"
        "Використовуйте кнопки нижче або просто надішліть мені артикул.",
        reply_markup=main_keyboard,
    )


# --- Обработчики для работы со списками ---

@dp.message(F.text == "Новий список")
async def new_list_handler(message: Message):
    """Создает новый (пустой) список для пользователя."""
    user_id = message.from_user.id
    user_lists[user_id] = {"list": [], "first_article": None}
    await message.answer(
        "Створено новий порожній список. Тепер шукайте товари та додавайте їх."
    )


@dp.message(F.text == "Мій список")
async def my_list_handler(message: Message):
    """Показывает текущий список пользователя."""
    user_id = message.from_user.id
    if user_id not in user_lists or not user_lists[user_id]["list"]:
        await message.answer(
            "Ваш список порожній. Спочатку створіть новий список і додайте товари."
        )
        return

    list_items = user_lists[user_id]["list"]
    response_lines = ["*Ваш поточний список:*\n"]
    for i, item in enumerate(list_items, 1):
        response_lines.append(
            f"{i}. Артикул: `{item['артикул']}`, Кількість: *{item['кількість']}*"
        )

    response_text = "\n".join(response_lines)

    save_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💾 Зберегти список у файл", callback_data="save_list"
                )
            ]
        ]
    )

    await message.answer(response_text, reply_markup=save_button)


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
async def add_to_list_callback_handler(
    callback_query: types.CallbackQuery, state: FSMContext
):
    """Ловит нажатие кнопки 'Добавить в список' и переходит в состояние ожидания количества."""
    article_to_add = callback_query.data.split("_")[-1]
    await state.update_data(article_to_add=article_to_add)
    await state.set_state(Form.waiting_for_quantity)
    await callback_query.message.answer(
        f"Введіть кількість для товару з артикулом `{article_to_add}`:"
    )
    await callback_query.answer()


@dp.message(StateFilter(Form.waiting_for_quantity), F.text.isdigit())
async def process_quantity(message: Message, state: FSMContext):
    """Получает количество, добавляет товар в список и сбрасывает состояние."""
    user_id = message.from_user.id
    quantity = int(message.text)
    data = await state.get_data()
    article = data.get("article_to_add")

    if not article:
        await message.answer("Сталася помилка. Спробуйте додати товар знову.")
        await state.clear()
        return

    if user_id not in user_lists:
        user_lists[user_id] = {"list": [], "first_article": None}

    user_lists[user_id]["list"].append({"артикул": article, "кількість": quantity})

    if not user_lists[user_id]["first_article"]:
        user_lists[user_id]["first_article"] = article

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
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 Додати в список",
                        callback_data=f"add_to_list_{product_data.get('артикул')}",
                    )
                ]
            ]
        )
        await message.answer(response_text, reply_markup=add_button)
    else:
        await message.answer(f"❌ *Товар з артикулом `{message.text}` не знайдено*")


# --- Точка входа ---
async def main():
    """Основная функция для запуска бота."""
    logging.info("Бот запускається...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())