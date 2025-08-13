from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from lexicon.lexicon import LEXICON
from database.models import Product


def get_admin_panel_kb() -> InlineKeyboardMarkup:
    """
    Створює та повертає клавіатуру для головного меню адмін-панелі.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LEXICON.BUTTON_IMPORT_PRODUCTS, callback_data="admin:import_products")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_EXPORT_STOCK, callback_data="admin:export_stock")],
            # У вашій версії коду тут була відсутня кнопка, я її додав згідно з лексиконом
            [InlineKeyboardButton(text=LEXICON.EXPORT_COLLECTED_BUTTON, callback_data="admin:export_collected")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_USER_ARCHIVES, callback_data="admin:user_archives")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_DELETE_ALL_LISTS, callback_data="admin:delete_all_lists")],
        ]
    )


def get_users_with_archives_kb(users: list) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру зі списком користувачів, які мають збережені архіви.

    Args:
        users: Список кортежів, де кожен кортеж - (user_id, lists_count).

    Returns:
        Клавіатура зі списком користувачів та кнопкою "Назад".
    """
    keyboard = []
    for user_id, lists_count in users:
        button_text = LEXICON.BUTTON_USER_LIST_ITEM.format(
            user_id=user_id, lists_count=lists_count
        )
        keyboard.append([
            InlineKeyboardButton(text=button_text, callback_data=f"admin:view_user:{user_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton(text=LEXICON.BUTTON_BACK_TO_ADMIN_PANEL, callback_data="admin:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_archive_kb(user_id: int, is_admin_view: bool = False) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру для меню архіву користувача.

    Args:
        user_id: ID користувача, для якого створюється клавіатура.
        is_admin_view: Прапорець, що вказує, чи переглядає архів адміністратор.
                       Якщо True, додає кнопку "Назад до списку користувачів".

    Returns:
        Клавіатура з кнопкою для завантаження ZIP та, опціонально, кнопкою "Назад".
    """
    keyboard = [[
        InlineKeyboardButton(text=LEXICON.BUTTON_PACK_IN_ZIP, callback_data=f"download_zip:{user_id}")
    ]]
    if is_admin_view:
        keyboard.append([
            InlineKeyboardButton(text=LEXICON.BUTTON_BACK_TO_USER_LIST, callback_data="admin:user_archives")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_search_results_kb(products: list[Product]) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру з результатами пошуку товарів.

    Args:
        products: Список об'єктів Product, знайдених під час пошуку.

    Returns:
        Клавіатура зі списком товарів для вибору.
    """
    keyboard = []
    for product in products:
        # Обрізаємо занадто довгі назви, щоб вони вмістились на кнопці
        button_text = (product.назва[:60] + '..') if len(product.назва) > 62 else product.назва
        keyboard.append([
            InlineKeyboardButton(text=button_text, callback_data=f"product:{product.id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_actions_kb(product_id: int, available_quantity: int) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру дій для картки товару.

    Args:
        product_id: ID товару.
        available_quantity: Доступна кількість товару для додавання в список.

    Returns:
        Клавіатура з кнопками "Додати все" та "Ввести іншу кількість".
    """
    keyboard = []

    # Кнопка "Додати все" з'являється тільки якщо є що додавати
    if available_quantity > 0:
        add_all_text = LEXICON.BUTTON_ADD_ALL.format(quantity=available_quantity)
        keyboard.append([
            InlineKeyboardButton(text=add_all_text, callback_data=f"add_all:{product_id}:{available_quantity}")
        ])

    keyboard.append([
        InlineKeyboardButton(text=LEXICON.BUTTON_ADD_CUSTOM, callback_data=f"add_custom:{product_id}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_kb(confirm_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
    """
    Створює універсальну клавіатуру підтвердження дії (Так/Ні).

    Args:
        confirm_callback: Рядок callback_data для кнопки "Так".
        cancel_callback: Рядок callback_data для кнопки "Ні".

    Returns:
        Клавіатура з кнопками "Так" та "Ні".
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=LEXICON.BUTTON_CONFIRM_YES, callback_data=confirm_callback),
            InlineKeyboardButton(text=LEXICON.BUTTON_CONFIRM_NO, callback_data=cancel_callback),
        ]]
    )