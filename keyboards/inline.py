from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_panel_kb():
    """Повертає головну клавіатуру адмін-панелі."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Імпорт товарів з Excel", callback_data="admin:import_products")],
            [InlineKeyboardButton(text="👥 архіви користувачів", callback_data="admin:user_archives")]
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