from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from lexicon.lexicon import LEXICON

# Клавіатура для звичайного користувача
user_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=LEXICON.BUTTON_NEW_LIST),
            KeyboardButton(text=LEXICON.BUTTON_MY_LIST),
        ],
        [KeyboardButton(text=LEXICON.BUTTON_ARCHIVE)],
    ],
    resize_keyboard=True,
    input_field_placeholder=LEXICON.PLACEHOLDER_USER,
)

# Клавіатура для адміністратора
admin_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=LEXICON.BUTTON_NEW_LIST),
            KeyboardButton(text=LEXICON.BUTTON_MY_LIST),
        ],
        [
            KeyboardButton(text=LEXICON.BUTTON_ARCHIVE),
            KeyboardButton(text=LEXICON.BUTTON_ADMIN_PANEL),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder=LEXICON.PLACEHOLDER_ADMIN,
)

# Клавіатура для скасування дії (для FSM станів)
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=LEXICON.BUTTON_CANCEL)]], resize_keyboard=True
)