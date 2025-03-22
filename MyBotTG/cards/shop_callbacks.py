import os
import aiosqlite
import asyncio
from aiogram import Router, types, F
from aiogram.types import FSInputFile

shop_callbacks_router = Router()

async def get_user_data(user_id):
    """🔹 Получает данные пользователя (очки + вселенная)."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT total_points, selected_universe FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_item_data(item_id, user_id):
    """🔹 Получает данные о товаре в магазине."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT item_type, item_value, price FROM user_shop WHERE item_id = ? AND user_id = ?", (item_id, user_id)) as cursor:
            return await cursor.fetchone()

async def update_user_points(user_id, amount):
    """🔹 Вычитает очки у пользователя."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE users SET total_points = total_points - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def delete_shop_item(item_id, user_id):
    """🔹 Удаляет товар из магазина после покупки."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("DELETE FROM user_shop WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        await db.commit()

async def add_user_card(user_id, card_id, universe):
    """🔹 Добавляет карту пользователю в инвентарь."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("""
            INSERT INTO user_cards (user_id, card_id, universe_id, quantity)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, card_id, universe_id) DO UPDATE SET quantity = quantity + 1
        """, (user_id, card_id, universe))
        await db.commit()

async def buy_spins(callback, user_id, spins, price):
    """🔹 Покупка прокруток."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE users SET spins = spins + ?, total_points = total_points - ? WHERE user_id = ?", (spins, price, user_id))
        await db.commit()

    await callback.message.answer(f"🎰 Вы купили {spins} прокруток!")
    await callback.answer("Покупка успешно завершена!", show_alert=False)

async def buy_card(callback, user_id, selected_universe, rarity, price):
    """🔹 Покупка случайной карты с заданной редкостью."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute(f"""
            SELECT card_id, name, photo_path, rarity, points
            FROM [{selected_universe}]
            WHERE rarity = ?
            ORDER BY RANDOM()
            LIMIT 1
        """, (rarity,)) as cursor:
            card = await cursor.fetchone()

    if not card:
        await callback.answer("❌ Ошибка: карта не найдена. Обратитесь к администратору.", show_alert=True)
        return

    card_id, card_name, photo_path, rarity, points = card
    await add_user_card(user_id, card_id, selected_universe)
    await update_user_points(user_id, price)

    if not os.path.isfile(photo_path):
        await callback.answer("❌ Ошибка: изображение карты не найдено.", show_alert=True)
        return

    photo_file = await asyncio.to_thread(FSInputFile, photo_path)

    await callback.message.answer_photo(
        photo=photo_file,
        caption=f"📜 Вы получили карту:\n🏷️ *{card_name}*\n🎲 *{rarity.capitalize()}*\n💎 *{points}*",
        parse_mode="Markdown"
    )

async def buy_specific_card(callback, user_id, selected_universe, card_id, price):
    """🔹 Покупка конкретной карты."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute(f"""
            SELECT card_id, name, photo_path, rarity, points
            FROM [{selected_universe}]
            WHERE card_id = ?
        """, (card_id,)) as cursor:
            card = await cursor.fetchone()

    if not card:
        await callback.answer("❌ Ошибка: карта не найдена.", show_alert=True)
        return

    card_id, card_name, photo_path, rarity, points = card
    await add_user_card(user_id, card_id, selected_universe)
    await update_user_points(user_id, price)

    if not os.path.isfile(photo_path):
        await callback.answer("❌ Ошибка: изображение карты не найдено.", show_alert=True)
        return

    photo_file = await asyncio.to_thread(FSInputFile, photo_path)

    await callback.message.answer_photo(
        photo=photo_file,
        caption=f"📜 Вы купили карту:\n🏷️ *{card_name}*\n🎲 *{rarity.capitalize()}*\n💎 *{points}*",
        parse_mode="Markdown"
    )

@shop_callbacks_router.callback_query(F.data.startswith("buy_"))
async def handle_purchase(callback: types.CallbackQuery):
    """🔹 Обработчик покупки в магазине."""
    user_id = callback.from_user.id
    item_id = int(callback.data.split("_")[1])

    user_data = await get_user_data(user_id)
    if not user_data:
        await callback.answer("❌ Ошибка: профиль не найден. Используйте /start.", show_alert=True)
        return

    total_points, selected_universe = user_data
    if not selected_universe:
        await callback.answer("❌ Ошибка: вы не выбрали вселенную. Используйте /select_universe.", show_alert=True)
        return

    item_data = await get_item_data(item_id, user_id)
    if not item_data:
        await callback.answer("❌ Ошибка: товар не найден или уже куплен.", show_alert=True)
        return

    item_type, item_value, price = item_data

    if total_points < price:
        await callback.answer("❌ Ошибка: у вас недостаточно очков.", show_alert=True)
        return

    if item_type == "spins":
        await buy_spins(callback, user_id, int(item_value), price)

    elif item_type == "rarity_guarantee":
        await buy_card(callback, user_id, selected_universe, item_value, price)

    elif item_type == "specific_card":
        await buy_specific_card(callback, user_id, selected_universe, item_value, price)

    else:
        await callback.answer("❌ Ошибка: неизвестный тип товара.", show_alert=True)
        return

    await delete_shop_item(item_id, user_id)
    await callback.message.edit_text("🛒 Ваш магазин обновлен. Используйте /shop для просмотра ассортимента.")
