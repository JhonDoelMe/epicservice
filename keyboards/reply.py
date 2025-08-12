from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Клавіатура для звичайного користувача
user_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новий список"), KeyboardButton(text="Мій список")],
        [KeyboardButton(text="🗂️ Архів списків")] # <-- ДОДАНО
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

# Клавіатура для скасування дії (для FSM станів)
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Скасувати")]
    ],
    resize_keyboard=True
)