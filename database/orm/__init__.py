# epicservice/database/orm/__init__.py

"""
Пакет ORM (Object-Relational Mapping).
"""

# --- ЗМІНА: Оновлюємо список імпортів ---
from .products import (
    orm_find_products, orm_get_all_products_async, orm_get_product_by_id,
    orm_smart_import, orm_subtract_collected
)
from .temp_lists import (
    orm_add_item_to_temp_list, orm_clear_temp_list, orm_delete_temp_list_item,
    orm_get_all_temp_list_items_async, orm_get_temp_list,
    orm_get_temp_list_department, orm_get_temp_list_item_quantity,
    orm_get_total_temp_reservation_for_product, orm_get_users_with_active_lists,
    orm_update_temp_list_item_quantity
)
from .archives import (
    orm_add_saved_list, orm_delete_all_saved_lists_async,
    orm_delete_lists_older_than_async, orm_get_all_collected_items_async,
    orm_get_all_files_for_user, orm_get_user_lists_archive,
    orm_get_users_for_warning_async, orm_get_users_with_archives,
    orm_update_reserved_quantity
)
from .users import (
    orm_upsert_user, orm_get_all_users_async
)

# Явно визначаємо, що саме буде експортуватися
__all__ = [
    # products
    "orm_find_products", "orm_get_product_by_id", "orm_smart_import",
    "orm_subtract_collected", "orm_get_all_products_async",
    # temp_lists
    "orm_clear_temp_list", "orm_add_item_to_temp_list",
    "orm_delete_temp_list_item", "orm_get_temp_list",
    "orm_get_temp_list_department", "orm_get_temp_list_item_quantity",
    "orm_get_total_temp_reservation_for_product",
    "orm_get_all_temp_list_items_async", "orm_get_users_with_active_lists",
    "orm_update_temp_list_item_quantity",
    # archives
    "orm_add_saved_list", "orm_update_reserved_quantity",
    "orm_get_user_lists_archive", "orm_get_all_files_for_user",
    "orm_get_users_with_archives", "orm_get_all_collected_items_async",
    "orm_delete_all_saved_lists_async", "orm_delete_lists_older_than_async",
    "orm_get_users_for_warning_async",
    # users
    "orm_upsert_user", "orm_get_all_users_async",
]