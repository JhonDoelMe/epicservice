from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from lexicon.lexicon import LEXICON

# --- Головна клавіатура для звичайного користувача ---
user_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=LEXICON.BUTTON_NEW_LIST),
            KeyboardButton(text=LEXICON.BUTTON_MY_LIST),
        ],
        [KeyboardButton(text=LEXICON.BUTTON_ARCHIVE)],
    ],
    resize_keyboard=True, # Адаптує розмір клавіатури
    input_field_placeholder=LEXICON.PLACEHOLDER_USER, # Текст-підказка в полі вводу
)

# --- Головна клавіатура для адміністратора ---
# Відрізняється наявністю кнопки для входу в адмін-панель.
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

# --- Універсальна клавіатура для скасування дії ---
# Використовується в сценаріях FSM (машини скінченних автоматів),
# щоб надати користувачу можливість вийти з поточного стану.
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=LEXICON.BUTTON_CANCEL)]],
    resize_keyboard=True
)