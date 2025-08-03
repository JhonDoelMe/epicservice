document.addEventListener('DOMContentLoaded', function () {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const listContainer = document.getElementById('list-container');
    const closeButton = document.getElementById('close-button');

    try {
        // Найнадійніший спосіб отримати стартовий параметр
        const listDataBase64 = tg.initDataUnsafe.start_param;

        if (listDataBase64) {
            const listData = JSON.parse(atob(listDataBase64));

            if (listData && listData.length > 0) {
                listContainer.innerHTML = ''; // Очищуємо контейнер перед додаванням
                listData.forEach(item => {
                    const itemElement = document.createElement('div');
                    itemElement.className = 'list-item';
                    itemElement.innerHTML = `
                        <div class="article">Артикул: ${item.артикул}</div>
                        <div class="quantity">Кількість: ${item.кількість}</div>
                    `;
                    listContainer.appendChild(itemElement);
                });
            } else {
                listContainer.innerHTML = '<p>Ваш список порожній.</p>';
            }
        } else {
            listContainer.innerHTML = '<p>Дані для списку не знайдено. Будь ласка, спробуйте відкрити знову з бота.</p>';
        }
    } catch (e) {
        console.error("Помилка обробки даних:", e);
        listContainer.innerHTML = `<p>Сталася помилка: ${e.message}</p>`;
    }

    closeButton.addEventListener('click', () => tg.close());
});