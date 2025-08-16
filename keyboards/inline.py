# epicservice/keyboards/inline.py

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Product, TempList
from lexicon.lexicon import LEXICON


def get_user_main_kb() -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_NEW_LIST,
                    callback_data="main:new_list"
                ),
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_MY_LIST,
                    callback_data="main:my_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_ARCHIVE,
                    callback_data="main:archive"
                )
            ],
        ]
    )

def get_admin_main_kb() -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_NEW_LIST,
                    callback_data="main:new_list"
                ),
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_MY_LIST,
                    callback_data="main:my_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_ADMIN_PANEL,
                    callback_data="admin:main"
                )
            ],
            [
                InlineKeyboardButton(
                    text=LEXICON.INLINE_BUTTON_ARCHIVE,
                    callback_data="main:archive"
                )
            ],
        ]
    )

def get_admin_panel_kb() -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LEXICON.BUTTON_IMPORT_PRODUCTS, callback_data="admin:import_products")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_EXPORT_STOCK, callback_data="admin:export_stock")],
            [InlineKeyboardButton(text=LEXICON.EXPORT_COLLECTED_BUTTON, callback_data="admin:export_collected")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_SUBTRACT_COLLECTED, callback_data="admin:subtract_collected")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_USER_ARCHIVES, callback_data="admin:user_archives")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_DELETE_ALL_LISTS, callback_data="admin:delete_all_lists")],
            [InlineKeyboardButton(text=LEXICON.BUTTON_BACK_TO_MAIN_MENU, callback_data="main:back")]
        ]
    )

def get_users_with_archives_kb(users: list) -> InlineKeyboardMarkup:
    # ... (код без змін)
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
    # ... (код без змін)
    keyboard = [[
        InlineKeyboardButton(text=LEXICON.BUTTON_PACK_IN_ZIP, callback_data=f"download_zip:{user_id}")
    ]]
    
    if is_admin_view:
        keyboard.append([
            InlineKeyboardButton(text=LEXICON.BUTTON_BACK_TO_USER_LIST, callback_data="admin:user_archives")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text=LEXICON.BUTTON_BACK_TO_MAIN_MENU, callback_data="main:back")
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_search_results_kb(products: list[Product]) -> InlineKeyboardMarkup:
    # ... (код без змін)
    keyboard = []
    for product in products:
        button_text = (product.назва[:60] + '..') if len(product.назва) > 62 else product.назва
        keyboard.append([
            InlineKeyboardButton(text=button_text, callback_data=f"product:{product.id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_product_actions_kb(
    product_id: int, 
    available_quantity: int, 
    search_query: str | None = None
) -> InlineKeyboardMarkup:
    """
    Створює клавіатуру дій для картки товару.
    """
    keyboard = []

    # Рядок з основними діями
    action_buttons = []
    if available_quantity > 0:
        add_all_text = LEXICON.BUTTON_ADD_ALL.format(quantity=available_quantity)
        action_buttons.append(
            InlineKeyboardButton(text=add_all_text, callback_data=f"add_all:{product_id}:{available_quantity}")
        )
    action_buttons.append(
        InlineKeyboardButton(text=LEXICON.BUTTON_ADD_CUSTOM, callback_data=f"add_custom:{product_id}")
    )
    keyboard.append(action_buttons)
    
    # Рядок з навігацією
    navigation_buttons = []
    if search_query:
        navigation_buttons.append(
            InlineKeyboardButton(
                text=LEXICON.BUTTON_BACK_TO_SEARCH, 
                callback_data="back_to_results"
            )
        )
    
    # --- ЗМІНА: Додаємо кнопки "Мій список" та "На головну" ---
    navigation_buttons.append(
        InlineKeyboardButton(
            text=LEXICON.INLINE_BUTTON_MY_LIST,
            callback_data="main:my_list"
        )
    )
    navigation_buttons.append(
        InlineKeyboardButton(
            text=LEXICON.BUTTON_BACK_TO_MAIN_MENU,
            callback_data="main:back"
        )
    )
    keyboard.append(navigation_buttons)
    # --- КІНЕЦЬ ЗМІНИ ---

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirmation_kb(confirm_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=LEXICON.BUTTON_CONFIRM_YES, callback_data=confirm_callback),
            InlineKeyboardButton(text=LEXICON.BUTTON_CONFIRM_NO, callback_data=cancel_callback),
        ]]
    )

def get_admin_lock_kb(action: str) -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=LEXICON.BUTTON_NOTIFY_USERS,
                callback_data=f"lock:notify:{action}"
            ),
            InlineKeyboardButton(
                text=LEXICON.BUTTON_FORCE_SAVE,
                callback_data=f"lock:force_save:{action}"
            )
        ]]
    )

def get_notify_confirmation_kb() -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=LEXICON.BUTTON_YES_NOTIFY,
                callback_data="notify_confirm:yes"
            ),
            InlineKeyboardButton(
                text=LEXICON.BUTTON_NO_NOTIFY,
                callback_data="notify_confirm:no"
            ),
        ]]
    )

def get_my_list_kb() -> InlineKeyboardMarkup:
    # ... (код без змін)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=LEXICON.SAVE_LIST_BUTTON,
                    callback_data="save_list"
                ),
                InlineKeyboardButton(
                    text=LEXICON.EDIT_LIST_BUTTON,
                    callback_data="edit_list:start"
                ),
                InlineKeyboardButton(
                    text=LEXICON.CANCEL_LIST_BUTTON,
                    callback_data="cancel_list:confirm"
                )
            ]
        ]
    )

def get_list_for_editing_kb(temp_list: list[TempList]) -> InlineKeyboardMarkup:
    # ... (код без змін)
    keyboard = []
    for item in temp_list:
        button_text = f"✏️ {item.product.артикул} ({item.quantity} шт.)"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"edit_item:{item.product.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="✅ Завершити редагування", callback_data="edit_list:finish")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)