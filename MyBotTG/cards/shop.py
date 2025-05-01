from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite
import random

shop_router = Router()

SPINS_COST = {3: 2400, 4: 3200, 5: 4000, 6: 4800, 7: 5600, 8: 6400}
RARITY_WEIGHTS = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мифическая": 1,
}

async def generate_user_shop(user_id: int, universe: str):
    """Асинхронная генерация товаров в магазине пользователя."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("DELETE FROM user_shop WHERE user_id = ? AND universe_id = ?", (user_id, universe))

        spins = random.randint(3, 8)
        spins_price = SPINS_COST[spins]
        await db.execute("""
            INSERT INTO user_shop (user_id, universe_id, item_type, item_value, price)
            VALUES (?, ?, 'spins', ?, ?)
        """, (user_id, universe, spins, spins_price))

        rarity = random.choices(list(RARITY_WEIGHTS.keys()), weights=RARITY_WEIGHTS.values(), k=1)[0]
        rarity_price = calculate_rarity_price(rarity)
        await db.execute("""
            INSERT INTO user_shop (user_id, universe_id, item_type, item_value, price)
            VALUES (?, ?, 'rarity_guarantee', ?, ?)
        """, (user_id, universe, rarity, rarity_price))

        async with db.execute(f"SELECT card_id, name, rarity, points FROM [{universe}]") as cursor:
            cards = await cursor.fetchall()
            if cards:
                card_id, card_name, rarity, points = random.choice(cards)
                card_price = points * 3
                await db.execute("""
                    INSERT INTO user_shop (user_id, universe_id, item_type, item_value, price)
                    VALUES (?, ?, 'specific_card', ?, ?)
                """, (user_id, universe, card_id, card_price))

        await db.commit()

def calculate_rarity_price(rarity: str) -> int:
    """Возвращает цену гарантированной карты определенной редкости."""
    rarity_points = {
        "обычная": 150,
        "редкая": 400,
        "эпическая": 800,
        "легендарная": 1500,
        "мифическая": 2500,
    }
    return rarity_points[rarity] * 2

async def update_all_shops():
    """Асинхронное обновление магазинов всех пользователей."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT user_id, selected_universe FROM users WHERE selected_universe IS NOT NULL") as cursor:
            users = await cursor.fetchall()
            for user_id, universe in users:
                await generate_user_shop(user_id, universe)

@shop_router.message(Command("shop"))
@shop_router.message(F.text.lower() == "магазин")
async def show_shop(message: types.Message):
    """Показывает магазин пользователя."""
    user_id = message.from_user.id

    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT selected_universe, total_points FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_data = await cursor.fetchone()

        if not user_data or not user_data[0]:
            await message.answer("❌ Вы не выбрали вселенную. Используйте /select_universe для выбора.")
            return

        selected_universe, user_balance = user_data

        async with db.execute("""
            SELECT item_id, item_type, item_value, price 
            FROM user_shop 
            WHERE user_id = ? AND universe_id = ?
        """, (user_id, selected_universe)) as cursor:
            items = await cursor.fetchall()

        if not items:
            await generate_user_shop(user_id, selected_universe)
            async with db.execute("""
                SELECT item_id, item_type, item_value, price 
                FROM user_shop 
                WHERE user_id = ? AND universe_id = ?
            """, (user_id, selected_universe)) as cursor:
                items = await cursor.fetchall()

    shop_text = (
        f"🛒 *Магазин вселенной {selected_universe.capitalize()}*\n"
        f"💰 Ваш баланс: *{user_balance}* очков\n\n"
        "🎁 Доступные товары:\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for item_id, item_type, item_value, price in items:
        if item_type == "spins":
            shop_text += f"🔄 Прокрутки: *{item_value} шт.* — *{price}* очков\n"
            button_text = f"🛍 Прокрутки"

        elif item_type == "rarity_guarantee":
            shop_text += f"🎲 Гарант на карту редкости: *{item_value.capitalize()}* — *{price}* очков\n"
            button_text = f"🛍 Гарант"

        elif item_type == "specific_card":
            async with aiosqlite.connect("bot_database.db") as db:
                async with db.execute(f"SELECT name FROM [{selected_universe}] WHERE card_id = ?", (item_value,)) as cursor:
                    card_name = await cursor.fetchone()

            shop_text += f"🃏 Карта: *{card_name[0]}* — *{price}* очков\n"
            button_text = f"🛍 Карта"

        keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"buy_{item_id}")])

    await message.answer(shop_text, reply_markup=keyboard, parse_mode="Markdown")

@shop_router.message(Command("update_shop"))
async def update_shop(message: types.Message):
    """Обновляет магазин пользователей."""
    await update_all_shops()
    await message.answer("🔄 Магазин обновлен!")
