from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_panel_kb():
    """Повертає інлайн-клавіатуру для адмін-панелі."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Імпорт товарів з Excel", callback_data="admin:import_products")]
        ]
    )

def get_search_results_kb(products: list):
    """Створює клавіатуру з результатами пошуку, використовуючи ID товару."""
    keyboard = []
    for product in products:
        button_text = f"{product.назва[:50]}..." if len(product.назва) > 50 else product.назва
        # В callback_data тепер короткий та унікальний ID
        keyboard.append([
            InlineKeyboardButton(text=button_text, callback_data=f"product:{product.id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_add_to_list_kb(product_id: int):
    """Створює кнопку 'Додати до списку', використовуючи ID товару."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Додати до списку", callback_data=f"add_to_list:{product_id}")]
        ]
    )