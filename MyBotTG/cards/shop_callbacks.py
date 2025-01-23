from aiogram import Router, types, F
import sqlite3
import os
from aiogram.types import FSInputFile

shop_callbacks_router = Router()

@shop_callbacks_router.callback_query(F.data.startswith("buy_"))
async def handle_purchase(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    item_id = int(callback.data.split("_")[1])  # Извлекаем ID товара из callback_data

    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()

        # Получаем информацию о пользователе
        cursor.execute("SELECT total_points, selected_universe FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            await callback.answer("Профиль не найден. Пожалуйста, зарегистрируйтесь с помощью команды /start.", show_alert=True)
            return

        total_points, selected_universe = user_data
        if not selected_universe:
            await callback.answer("Вы не выбрали вселенную. Используйте /selectuniverse для выбора.", show_alert=True)
            return

        # Получаем информацию о товаре
        cursor.execute("SELECT item_type, item_value, price FROM user_shop WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        item_data = cursor.fetchone()
        if not item_data:
            await callback.answer("Товар не найден или уже куплен.", show_alert=True)
            return

        item_type, item_value, price = item_data

        # Проверяем достаточно ли очков у пользователя
        if total_points < price:
            await callback.answer("У вас недостаточно очков для покупки.", show_alert=True)
            return

        # Выполняем покупку
        if item_type == "spins":
            # Покупка прокруток
            cursor.execute("UPDATE users SET spins = spins + ?, total_points = total_points - ? WHERE user_id = ?", (int(item_value), price, user_id))
            conn.commit()
            await callback.message.answer(f"🎰 Вы купили {item_value} прокруток!")

        elif item_type == "rarity_guarantee":
            # Покупка гаранта на редкость
            cursor.execute(f"""
                SELECT card_id, name, photo_path, rarity, points
                FROM [{selected_universe}]
                WHERE rarity = ?
                ORDER BY RANDOM()
                LIMIT 1
            """, (item_value,))
            card = cursor.fetchone()
            if card:
                card_id, card_name, photo_path, rarity, points = card
                cursor.execute("""
                    INSERT INTO user_cards (user_id, card_id, universe, quantity)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id, card_id, universe) DO UPDATE SET quantity = quantity + 1
                """, (user_id, card_id, selected_universe))
                cursor.execute("UPDATE users SET total_points = total_points - ? WHERE user_id = ?", (price, user_id))
                conn.commit()

                # Проверяем существование файла изображения
                if not os.path.isfile(photo_path):
                    await callback.answer("Ошибка: изображение карты не найдено. Обратитесь к администратору.", show_alert=True)
                    return

                # Отправляем сообщение о выпавшей карте
                photo_file = FSInputFile(photo_path)
                await callback.message.answer_photo(
                    photo=photo_file,
                    caption=(
                        f"📜 Вы получили карту:\n"
                        f"🏷️ Имя: *{card_name}*\n"
                        f"🎲 Редкость: *{rarity.capitalize()}*\n"
                        f"🎖️ Ценность: *{points} очков*"
                    ),
                    parse_mode="Markdown"
                )
            else:
                await callback.answer("Не удалось найти карту данной редкости. Обратитесь к администратору.", show_alert=True)
                return

        elif item_type == "specific_card":
            # Покупка конкретной карты
            cursor.execute(f"""
                SELECT card_id, name, photo_path, rarity, points
                FROM [{selected_universe}]
                WHERE card_id = ?
            """, (item_value,))
            card = cursor.fetchone()
            if card:
                card_id, card_name, photo_path, rarity, points = card
                cursor.execute("""
                    INSERT INTO user_cards (user_id, card_id, universe, quantity)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id, card_id, universe) DO UPDATE SET quantity = quantity + 1
                """, (user_id, card_id, selected_universe))
                cursor.execute("UPDATE users SET total_points = total_points - ? WHERE user_id = ?", (price, user_id))
                conn.commit()

                # Проверяем существование файла изображения
                if not os.path.isfile(photo_path):
                    await callback.answer("Ошибка: изображение карты не найдено. Обратитесь к администратору.", show_alert=True)
                    return

                photo_file = FSInputFile(photo_path)
                await callback.message.answer_photo(
                    photo=photo_file,
                    caption=(
                        f"📜 Вы купили карту:\n"
                        f"🏷️ Имя: *{card_name}*\n"
                        f"🎲 Редкость: *{rarity.capitalize()}*\n"
                        f"🎖️ Ценность: *{points} очков*"
                    ),
                    parse_mode="Markdown"
                )
        else:
            await callback.answer("Неизвестный тип товара.", show_alert=True)
            return

        # Удаляем товар из ассортимента пользователя
        cursor.execute("DELETE FROM user_shop WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        conn.commit()

        # Уведомление об успешной покупке
        await callback.answer("Покупка успешно завершена!", show_alert=False)

    # Обновляем сообщение магазина
    await callback.message.edit_text("🛒 Ваш магазин обновлен. Используйте /shop для просмотра текущего магазина.")
