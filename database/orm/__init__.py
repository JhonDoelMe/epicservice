# epicservice/database/orm/__init__.py

"""
Пакет ORM (Object-Relational Mapping).
"""

# Імпортуємо всі функції з модуля для роботи з товарами
from .products import (
    orm_find_products,
    orm_get_all_products_sync,
    orm_get_product_by_id,
    orm_smart_import,
    orm_subtract_collected,
)

# Імпортуємо всі функції з модуля для роботи з тимчасовими списками
from .temp_lists import (
    orm_add_item_to_temp_list,
    orm_clear_temp_list,
    orm_get_all_temp_list_items_sync,
    orm_get_temp_list,
    orm_get_temp_list_department,
    orm_get_temp_list_item_quantity,
    orm_get_total_temp_reservation_for_product,
    orm_get_users_with_active_lists,
)

# Імпортуємо всі функції з модуля для роботи з архівами (збереженими списками)
from .archives import (
    orm_add_saved_list,
    orm_delete_all_saved_lists_sync,
    orm_delete_lists_older_than_sync,
    orm_get_all_collected_items_sync,
    orm_get_all_files_for_user,
    orm_get_user_lists_archive,
    orm_get_users_for_warning_sync,
    orm_get_users_with_archives,
    orm_update_reserved_quantity,
)

# Імпортуємо функції з нового модуля для роботи з користувачами
from .users import (
    orm_upsert_user,
    orm_get_all_users_sync,
)


# Явно визначаємо, що саме буде експортуватися
__all__ = [
    # products
    "orm_find_products",
    "orm_get_product_by_id",
    "orm_smart_import",
    "orm_subtract_collected",
    "orm_get_all_products_sync",
    # temp_lists
    "orm_clear_temp_list",
    "orm_add_item_to_temp_list",
    "orm_get_temp_list",
    "orm_get_temp_list_department",
    "orm_get_temp_list_item_quantity",
    "orm_get_total_temp_reservation_for_product",
    "orm_get_all_temp_list_items_sync",
    "orm_get_users_with_active_lists",
    # archives
    "orm_add_saved_list",
    "orm_update_reserved_quantity",
    "orm_get_user_lists_archive",
    "orm_get_all_files_for_user",
    "orm_get_users_with_archives",
    "orm_get_all_collected_items_sync",
    "orm_delete_all_saved_lists_sync",
    "orm_delete_lists_older_than_sync",
    "orm_get_users_for_warning_sync",
    # users
    "orm_upsert_user",
    "orm_get_all_users_sync",
]