# lexicon/lexicon.py

class Lexicon:
    # --- Common ---
    CMD_START_USER = "Вітаю! Я допоможу вам знайти товари та створити списки."
    CMD_START_ADMIN = "Вітаю, Адміністраторе!"
    # -- Новые строки для кнопок --
    BUTTON_IMPORT_PRODUCTS = "📥 Імпорт товарів з Excel"
    BUTTON_EXPORT_STOCK = "📊 Вивантажити залишки"
    BUTTON_USER_ARCHIVES = "👥 Архіви користувачів"
    BUTTON_USER_LIST_ITEM = "Користувач {user_id} (списκів: {lists_count})"
    BUTTON_BACK_TO_ADMIN_PANEL = "⬅️ Назад до адмін-панелі"
    BUTTON_PACK_IN_ZIP = "📦 Запакувати все в ZIP-архів"
    BUTTON_BACK_TO_USER_LIST = "⬅️ Назад до списку користувачів"
    BUTTON_ADD_ALL = "✅ Додати все ({quantity})"
    BUTTON_ADD_CUSTOM = "📝 Ввести іншу кількість"
    BUTTON_CONFIRM_YES = "✅ Так"
    BUTTON_CONFIRM_NO = "❌ Ні"


    # --- User Search ---
    SEARCH_TOO_SHORT = "⚠️ Будь ласка, введіть для пошуку не менше 3 символів."
    SEARCH_NO_RESULTS = "На жаль, за вашим запитом нічого не знайдено."
    SEARCH_MANY_RESULTS = "Знайдено кілька варіантів. Будь ласка, оберіть потрібний:"
    PRODUCT_CARD_TITLE = "✅ *Знайдено товар*"
    PRODUCT_CARD_TEMPLATE = (
        f"{PRODUCT_CARD_TITLE}\n\n"
        "📝 *Назва:* {name}\n"
        "🏢 *Відділ:* {department}\n"
        "📂 *Група:* {group}\n"
        "📦 *Доступно для збирання:* {available}\n"
        "🛒 *В резерві (з вашим списком):* {reserved}"
    )

    # --- User Lists ---
    NEW_LIST_CONFIRM = (
        "⚠️ Ви впевнені, що хочете створити новий список?\n"
        "**Весь поточний незбережений список буде видалено!**"
    )
    NEW_LIST_CONFIRMED = "✅ Створено новий порожній список. Тепер шукайте товари та додавайте їх."
    ACTION_CANCELED = "Дію скасовано. Ваш поточний список залишається без змін."
    EMPTY_LIST = "Ваш список порожній."
    MY_LIST_TITLE = "*Ваш поточний список (Відділ: {department}):*\n"
    MY_LIST_ITEM = "{i}. `{article}` ({name})\n   Кількість: *{quantity}*"
    SAVE_LIST_BUTTON = "💾 Зберегти та відкласти"
    FORGET_NOT_TO_SAVE = "Не забувайте зберегти!"
    PRODUCT_NOT_FOUND = "Помилка: товар не знайдено."
    DEPARTMENT_MISMATCH = "Заборонено! Усі товари повинні бути з відділу {department}."
    ITEM_ADDED_TO_LIST = "Товар `{article}` у кількості *{quantity}* додано до списку."
    ENTER_QUANTITY = "Введіть кількість для товару:\n`{product_name}`"
    CANCEL_ACTION = "Дію скасовано."
    SAVING_LIST_PROCESS = "Перевіряю залишки та формую списки..."
    TRANSACTION_ERROR = "Сталася критична помилка під час перевірки залишків. Спробуйте знову."
    MAIN_LIST_SAVED = "✅ **Основний список** збережено."
    MAIN_LIST_SAVE_ERROR = "Сталася помилка при збереженні основного списку: {error}"
    SURPLUS_LIST_CAPTION = "⚠️ **УВАГА!**\nЦе список товарів, яких **не вистачило на складі** (лишки)."
    SURPLUS_LIST_SAVE_ERROR = "Сталася помилка при збереженні списку лишків: {error}"
    PROCESSING_COMPLETE = "Обробку завершено!"

    # --- Archive ---
    NO_ARCHIVED_LISTS = "У вас ще немає збережених списків."
    ARCHIVE_TITLE = "🗂️ *Ваш архів списків:*\n\n"
    ARCHIVE_ITEM = "{i}. `{file_name}` (від {created_date})\n"

    # --- Admin Panel ---
    ADMIN_PANEL_GREETING = "Ви в панелі адміністратора. Оберіть дію:"
    EXPORT_COLLECTED_BUTTON = "📦 Вивантажити зведення по зібраному"
    IMPORT_PROMPT = (
        "Будь ласка, надішліть мені файл Excel (`.xlsx`) з товарами.\n\n"
        "Для скасування натисніть кнопку нижче."
    )
    IMPORT_WRONG_FORMAT = "Помилка. Будь ласка, надішліть файл у форматі `.xlsx`."
    IMPORT_PROCESSING = "Завантажую та перевіряю файл..."
    IMPORT_INVALID_COLUMNS = "❌ Помилка: назви колонок неправильні. Очікується: `в, г, н, к`, а у файлі: `{columns}`"
    IMPORT_VALIDATION_ERRORS_TITLE = "❌ **У файлі знайдені помилки:**\n\n"
    IMPORT_CRITICAL_READ_ERROR = "❌ Критична помилка при читанні файлу: {error}"
    IMPORT_STARTING = "Файл виглядає добре. Починаю імпорт та очищення старих резервів..."
    IMPORT_CANCELLED = "Імпорт скасовано."
    IMPORT_INCORRECT_FILE = "Будь ласка, надішліть документ (файл Excel) або натисніть 'Скасувати'."
    IMPORT_SYNC_ERROR = "❌ Сталася критична помилка під час синхронізації: {error}"
    IMPORT_REPORT_TITLE = "✅ *Синхронізацію завершено!*\n"
    IMPORT_REPORT_ADDED = "➕ *Додано нових:* {added}"
    IMPORT_REPORT_UPDATED = "🔄 *Оновлено існуючих:* {updated}"
    IMPORT_REPORT_DELETED = "❌ *Видалено старих:* {deleted}\n"
    IMPORT_REPORT_TOTAL = "🗃️ *Всього артикулів у базі:* {total}"
    IMPORT_REPORT_SUCCESS_CHECK = "✅ *Перевірка пройшла успішно:* кількість у базі співпадає з файлом ({count})."
    IMPORT_REPORT_FAIL_CHECK = "⚠️ *Увага, розбіжність:* у базі {db_count}, а у файлі {file_count} унікальних артикулів."
    NO_USERS_WITH_ARCHIVES = "Жоден користувач ще не зберіг списку."
    CHOOSE_USER_TO_VIEW_ARCHIVE = "Оберіть користувача для перегляду його архіву:"
    USER_HAS_NO_ARCHIVES = "У цього користувача немає збережених списків."
    USER_ARCHIVE_TITLE = "🗂️ *Архів користувача `{user_id}`:*\n\n"
    NO_FILES_TO_ARCHIVE = "Немає файлів для архівації."
    PACKING_ARCHIVE = "Почав пакування архівів для користувача `{user_id}`..."
    ZIP_ARCHIVE_CAPTION = "ZIP-архів для користувача `{user_id}`."
    ZIP_ERROR = "Сталася помилка: {error}"
    EXPORTING_STOCK = "Починаю формування звіту по залишкам..."
    STOCK_REPORT_CAPTION = "✅ Ось ваш звіт по актуальним залишкам."
    COLLECTED_REPORT_CAPTION = "✅ Ось зведений звіт по всім зібраним товарам."
    COLLECTED_REPORT_EMPTY = "Наразі немає жодного зібраного товару у збережених списках."
    COLLECTED_REPORT_PROCESSING = "Починаю формування зведеного звіту..."
    STOCK_REPORT_ERROR = "❌ Не вдалося створити звіт."
    
    # --- Error Handler ---
    UNEXPECTED_ERROR = (
        "😔 Виникла непередбачена помилка.\n"
        "Ми вже отримали сповіщення і працюємо над її вирішенням."
    )

LEXICON = Lexicon()