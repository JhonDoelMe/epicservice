from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from lexicon.lexicon import LEXICON

def get_admin_panel_kb():
    """Повертає головну клавіатуру адмін-панелі."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Імпорт товарів з Excel", callback_data="admin:import_products")],
            [InlineKeyboardButton(text="📊 Вивантажити залишки", callback_data="admin:export_stock")],
            [InlineKeyboardButton(text=LEXICON.EXPORT_COLLECTED_BUTTON, callback_data="admin:export_collected")],
            [InlineKeyboardButton(text="👥 Архіви користувачів", callback_data="admin:user_archives")]
        ]
    )

def get_users_with_archives_kb(users: list):
    """Створює клавіатуру зі списком користувачів, які мають архіви."""
    keyboard = []
    for user in users:
        user_id, lists_count = user
        keyboard.append([
            InlineKeyboardButton(text=f"Користувач {user_id} (списκів: {lists_count})", callback_data=f"admin:view_user:{user_id}")
        ])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад до адмін-панелі", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_archive_kb(user_id: int, is_admin_view: bool = False):
    """Повертає клавіатуру для меню архіву."""
    keyboard = [
        [InlineKeyboardButton(text="📦 Запакувати все в ZIP-архів", callback_data=f"download_zip:{user_id}")]
    ]
    if is_admin_view:
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад до списку користувачів", callback_data="admin:user_archives")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_search_results_kb(products: list):
    """Створює клавіатуру з результатами пошуку, використовуючи ID товару."""
    keyboard = []
    for product in products:
        button_text = f"{product.назва[:50]}..." if len(product.назва) > 50 else product.назва
        keyboard.append([
            InlineKeyboardButton(text=button_text, callback_data=f"product:{product.id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_product_actions_kb(product_id: int, available_quantity: int):
    """
    Створює кнопки дій для картки товару:
    - Додати всю доступну кількість.
    - Ввести іншу кількість.
    """
    keyboard = []
    
    if available_quantity > 0:
        keyboard.append([
            InlineKeyboardButton(
                text=f"✅ Додати все ({available_quantity})", 
                callback_data=f"add_all:{product_id}:{available_quantity}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="📝 Ввести іншу кількість", callback_data=f"add_custom:{product_id}")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirmation_kb(confirm_callback: str, cancel_callback: str):
    """
    Створює клавіатуру підтвердження (Так/Ні).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Так", callback_data=confirm_callback),
                InlineKeyboardButton(text="❌ Ні", callback_data=cancel_callback)
            ]
        ]
    )