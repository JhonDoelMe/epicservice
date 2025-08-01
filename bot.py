import asyncio
import logging
import os

import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties # <-- 1. НОВЫЙ ИМПОРТ
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# --- Конфигурация ---
# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем токен бота и путь к файлу
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CSV_FILE_PATH = "data.csv"

# Настраиваем логирование для отладки
logging.basicConfig(level=logging.INFO)

# --- Инициализация бота и диспетчера ---
# Используем новый способ установки parse_mode
# <-- 2. ИЗМЕНЕННАЯ СТРОКА
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()


# --- Основная логика поиска ---
def find_product_by_article(article_number: str) -> dict | None:
    """
    Ищет товар по артикулу в CSV-файле.
    Возвращает словарь с данными о товаре или None, если ничего не найдено.
    """
    try:
        # Читаем CSV файл, указав правильный разделитель - точку с запятой
        df = pd.read_csv(CSV_FILE_PATH, delimiter=';')
        
        # Приводим колонку 'артикул' к строковому типу для надежного сравнения
        df['артикул'] = df['артикул'].astype(str)
        
        # Ищем строку, где значение в колонке 'артикул' совпадает с запрошенным
        result_row = df[df['артикул'] == article_number]
        
        # Если найдена хотя бы одна строка
        if not result_row.empty:
            # Возвращаем первую найденную строку в виде словаря
            return result_row.iloc[0].to_dict()
            
    except FileNotFoundError:
        logging.error(f"Файл не найден по пути: {CSV_FILE_PATH}")
        return None
    except Exception as e:
        logging.error(f"Произошла ошибка при чтении файла или поиске: {e}")
        return None
        
    # Если ничего не найдено, возвращаем None
    return None


# --- Обработчики сообщений (хендлеры) ---

# Обработчик команды /start
@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    """Отправляет приветственное сообщение в ответ на команду /start."""
    await message.answer(
        "👋 *Вітаю!*\n\n"
        "Я бот для пошуку товарів за артикулом.\n"
        "Просто надішліть мені числовий артикул, і я знайду інформацію про товар."
    )

# Обработчик сообщений, содержащих только цифры (наш артикул)
@dp.message(F.text.isdigit())
async def search_article_handler(message: types.Message):
    """Ищет артикул и отправляет результат пользователю."""
    article_to_find = message.text
    logging.info(f"Користувач {message.from_user.id} шукає артикул: {article_to_find}")
    
    # Ищем товар
    product_data = find_product_by_article(article_to_find)
    
    # Если товар найден
    if product_data:
        # Формируем красивый ответ
        response_text = (
            f"✅ *Знайдено товар за артикулом {product_data['артикул']}*\n\n"
            f"🏢 *Відділ:* {product_data['відділ']}\n"
            f"📂 *Група:* {product_data['група']}\n"
            f"📝 *Назва:* {product_data['назва']}\n"
            f"📦 *Кількість:* {product_data['кількість']}"
        )
        await message.answer(response_text)
    else:
        # Если товар не найден
        await message.answer(
            f"❌ *Товар не знайдено*\n\n"
            f"На жаль, товар з артикулом `{article_to_find}` відсутній у базі."
        )

# Обработчик для любого другого текста
@dp.message()
async def handle_other_text(message: types.Message):
    """Сообщает пользователю, что нужно ввести именно число."""
    await message.answer("Будь ласка, надішліть *тільки числовий артикул* товару.")


# --- Точка входа ---
async def main():
    """Основная функция для запуска бота."""
    logging.info("Бот запускається...")
    # Начинаем опрос Telegram на наличие новых сообщений
    await dp.start_polling(bot)


if __name__ == "__main__":
    # Запускаем асинхронную функцию main
    asyncio.run(main())