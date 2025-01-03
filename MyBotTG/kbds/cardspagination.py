from aiogram import Router, types
from handlers.cardshand.callbackcards import PaginationCallback, RarityCallback, ReturnCallback
from kbds.inlinecards import pagination_keyboard, rarity_keyboard_for_user
import sqlite3

cardspagination_router = Router()

# Список редкостей
rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]

@cardspagination_router.callback_query(PaginationCallback.filter())
async def paginate_cards(callback: types.CallbackQuery, callback_data: PaginationCallback):
    user_id = callback.from_user.id
    rarity = callback_data.rarity_type
    index = callback_data.index

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Получаем выбранную вселенную пользователя
    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    selected_universe = cursor.fetchone()
    if not selected_universe or not selected_universe[0]:
        await callback.answer("Вы не выбрали вселенную.", show_alert=True)
        conn.close()
        return

    selected_universe = selected_universe[0]

    # Получаем карты выбранной редкости
    cursor.execute(f"""
    SELECT c.card_id, c.name, c.photo_id, c.rarity, c.points
    FROM user_cards uc
    JOIN [{selected_universe}] c ON uc.card_id = c.card_id
    WHERE uc.user_id = ? AND c.rarity = ?
    """, (user_id, rarity))

    cards = cursor.fetchall()
    conn.close()

    if not cards:
        await callback.answer("Нет карт для отображения.", show_alert=True)
        return

    total = len(cards)
    index = index % total  # Корректируем индекс в пределах доступных карт

    # Получаем данные для текущей карты
    card_id, name, photo_id, rarity, points = cards[index]

    # Формируем описание карты
    caption = f"Карта: *{name}*\nРедкость: *{rarity.capitalize()}*\nЦенность: *{points}* PTS"

    # Кнопки пагинации
    pagination_markup = pagination_keyboard(rarity=rarity, index=index, total=total, include_return=True)

    # Отправляем обновленное сообщение
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(
                media=photo_id,
                caption=caption,
                parse_mode="Markdown"
            ),
            reply_markup=pagination_markup
        )
    except Exception as e:
        print(f"Ошибка при обновлении карты: {e}")
        await callback.answer("Произошла ошибка при переключении карт.", show_alert=True)



@cardspagination_router.callback_query(ReturnCallback.filter())
async def return_to_categories(callback: types.CallbackQuery, callback_data: ReturnCallback):
    """
    Обработчик кнопки "Вернуться" для возврата к выбору категорий.
    """
    if callback_data.action != "to_categories":
        return  # Игнорируем неверное действие

    user_id = callback.from_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Получаем выбранную вселенную пользователя
    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    selected_universe = cursor.fetchone()[0]  # Получаем вселенную пользователя

    if not selected_universe:
        await callback.answer("Вы не выбрали вселенную. Используйте команду /selectuniverse для выбора.", show_alert=True)
        conn.close()
        return

    # Считаем карты пользователя по редкостям
    cursor.execute(f"""
    SELECT c.rarity, COUNT(uc.card_id)
    FROM user_cards uc
    JOIN [{selected_universe}] c ON uc.card_id = c.card_id
    WHERE uc.user_id = ?
    GROUP BY c.rarity
    """, (user_id,))
    user_cards = {row[0]: row[1] for row in cursor.fetchall()}

    # Считаем общее количество карт в базе по редкостям
    cursor.execute(f"""
    SELECT rarity, COUNT(card_id)
    FROM [{selected_universe}]
    GROUP BY rarity
    """)
    total_cards = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    # Формируем клавиатуру с кнопками редкостей
    keyboard = rarity_keyboard_for_user(user_cards, total_cards, selected_universe)

    try:
        await callback.message.delete()  # Удаляем старое сообщение с изображением
        await callback.message.answer(  # Отправляем новое сообщение с выбором категорий
            text="Выберите категорию карт:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка при возврате в категории: {e}")
        await callback.answer("Произошла ошибка при возврате в категории.", show_alert=True)
