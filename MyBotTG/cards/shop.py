from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import OWNER_ID, AVAILABLE_UNIVERSES
import sqlite3
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


def generate_user_shop(user_id: int, universe: str):
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()

        # Удаляем старый ассортимент
        cursor.execute("DELETE FROM user_shop WHERE user_id = ? AND universe = ?", (user_id, universe))

        # Прокрутки
        spins = random.randint(3, 8)
        spins_price = SPINS_COST[spins]
        cursor.execute("""
            INSERT INTO user_shop (user_id, universe, item_type, item_value, price)
            VALUES (?, ?, 'spins', ?, ?)
        """, (user_id, universe, spins, spins_price))

        # Гарант на редкость
        rarity = random.choices(list(RARITY_WEIGHTS.keys()), weights=RARITY_WEIGHTS.values(), k=1)[0]
        rarity_price = calculate_rarity_price(rarity)
        cursor.execute("""
            INSERT INTO user_shop (user_id, universe, item_type, item_value, price)
            VALUES (?, ?, 'rarity_guarantee', ?, ?)
        """, (user_id, universe, rarity, rarity_price))

        # Гарант на карту
        cursor.execute(f"SELECT card_id, name, rarity, points FROM [{universe}]")
        cards = cursor.fetchall()
        if cards:
            card = random.choice(cards)
            card_id, card_name, rarity, points = card
            card_price = points * 3
            cursor.execute("""
                INSERT INTO user_shop (user_id, universe, item_type, item_value, price)
                VALUES (?, ?, 'specific_card', ?, ?)
            """, (user_id, universe, card_id, card_price))


def calculate_rarity_price(rarity: str) -> int:
    rarity_points = {
        "обычная": 150,
        "редкая": 400,
        "эпическая": 800,
        "легендарная": 1500,
        "мифическая": 2500,
    }
    return rarity_points[rarity] * 2


@shop_router.message(Command("shop"))
@shop_router.message(F.text.lower() == "магазин")
async def show_shop(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()

        # Проверяем выбранную вселенную
        cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
        selected_universe = cursor.fetchone()
        if not selected_universe or not selected_universe[0]:
            await message.answer("Вы не выбрали вселенную. Используйте /selectuniverse для выбора.")
            return

        universe = selected_universe[0]

        # Проверяем товары
        cursor.execute("SELECT item_id, item_type, item_value, price FROM user_shop WHERE user_id = ? AND universe = ?", (user_id, universe))
        items = cursor.fetchall()

        if not items:
            generate_user_shop(user_id, universe)
            cursor.execute("SELECT item_id, item_type, item_value, price FROM user_shop WHERE user_id = ? AND universe = ?", (user_id, universe))
            items = cursor.fetchall()

        shop_text = f"🛒 Магазин вселенной {universe.capitalize()}:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for item in items:
            item_id, item_type, item_value, price = item
            if item_type == "spins":
                shop_text += f"🎰 Прокрутки: {item_value} шт. — {price} PTS\n"
                button_text = f"Купить {item_value} прокруток"
            elif item_type == "rarity_guarantee":
                shop_text += f"🎲 Гарант на редкость: {item_value.capitalize()} — {price} PTS\n"
                button_text = f"Купить {item_value.capitalize()} карту"
            elif item_type == "specific_card":
                cursor.execute(f"SELECT name FROM [{universe}] WHERE card_id = ?", (item_value,))
                card_name = cursor.fetchone()[0]
                shop_text += f"📜 Гарант на карту: {card_name} — {price} PTS\n"
                button_text = f"Купить {card_name}"

            keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"buy_{item_id}")])

    await message.answer(shop_text, reply_markup=keyboard)


@shop_router.message(Command("update_shop"))
@shop_router.message(F.text.lower() == "обновить магазин")
async def update_shop(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    for universe in AVAILABLE_UNIVERSES:
        generate_user_shop(message.from_user.id, universe)

    await message.answer("Магазин обновлен.")
