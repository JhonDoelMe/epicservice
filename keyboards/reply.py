from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Клавіатура для звичайного користувача
user_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новий список"), KeyboardButton(text="Мій список")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Введіть артикул або назву товару..."
)

# Клавіатура для адміністратора
admin_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новий список"), KeyboardButton(text="Мій список")],
        [KeyboardButton(text="🗂️ Архів списків"), KeyboardButton(text="👑 Адмін-панель")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Введіть артикул, назву або команду..."
)