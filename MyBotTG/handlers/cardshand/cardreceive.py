from aiogram import Router, types, F
from aiogram.filters import Command
from datetime import datetime, timedelta
from random import choices
import sqlite3
from config import OWNER_ID

cardreceive_router = Router()

# Вес редкостей карт
RARITY_WEIGHTS = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мифическая": 1
}

# Время ожидания между получением карт (в часах)
CARD_RECEIVE_COOLDOWN = 4


def get_random_card(cards: list) -> tuple:
    """Выбирает случайную карту с учетом редкости."""
    rarities = [card[2] for card in cards]
    weights = [RARITY_WEIGHTS[rarity] for rarity in rarities]
    return choices(cards, weights=weights, k=1)[0]


async def check_cooldown(user_id: int) -> bool:
    """Проверяет, действует ли кулдаун."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT last_card_time FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        last_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - last_time
        return time_diff < timedelta(hours=CARD_RECEIVE_COOLDOWN)
    return False


@cardreceive_router.message(Command("givecard"))
@cardreceive_router.message(F.text.lower() == "дай карту")
async def give_card(message: types.Message):
    user_id = message.from_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Проверяем, есть ли прокрутки
    cursor.execute("SELECT spins FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    spins = result[0] if result else 0

    if spins > 0:
        cursor.execute("UPDATE users SET spins = spins - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    else:
        if await check_cooldown(user_id):
            await message.answer("Вы уже получали карту! Попробуйте позже.")
            conn.close()
            return

    # Проверяем выбранную вселенную
    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    universe_result = cursor.fetchone()
    if not universe_result or not universe_result[0]:
        await message.answer("Вы не выбрали вселенную. Используйте /selectuniverse для выбора.")
        conn.close()
        return
    selected_universe = universe_result[0]

    # Получаем карты
    cursor.execute(f"SELECT card_id, name, rarity, photo_id, points FROM [{selected_universe}]")
    cards = cursor.fetchall()

    if not cards:
        await message.answer(f"В базе данных {selected_universe.capitalize()} нет карт.")
        conn.close()
        return

    # Выбираем карту
    card = get_random_card(cards)
    card_id, name, rarity, photo_id, points = card

    # Проверяем повторку
    cursor.execute("""
        SELECT quantity FROM user_cards WHERE user_id = ? AND card_id = ? AND universe = ?
    """, (user_id, card_id, selected_universe))
    result = cursor.fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if result:
        cursor.execute("UPDATE users SET total_points = total_points + ? WHERE user_id = ?", (points, user_id))
        cursor.execute("UPDATE users SET last_card_time = ? WHERE user_id = ?", (now, user_id))
        conn.commit()

        await message.answer_photo(
            photo=photo_id,
            caption=(
                f"🎉 Вам выпала повторная карточка «*{name}*»!\n"
                
                f"🎲 Редкость: {rarity.capitalize()}\n"
                f"🎖️ Очки: +{[points]} добавлено к вашему счёту.\n\n"
                
                f"🔄 Осталось прокруток: {spins - 1 if spins > 0 else 0}"
            ),
            parse_mode="Markdown"
        )
    else:
        cursor.execute("""
            INSERT INTO user_cards (user_id, card_id, universe, quantity)
            VALUES (?, ?, ?, 1)
        """, (user_id, card_id, selected_universe))
        cursor.execute("UPDATE users SET total_points = total_points + ? WHERE user_id = ?", (points, user_id))
        cursor.execute("UPDATE users SET last_card_time = ? WHERE user_id = ?", (now, user_id))
        conn.commit()

        await message.answer_photo(
            photo=photo_id,
            caption=(
                f"🎉 Ваша коллекция пополнилась карточкой «*{name}*»!\n\n"
                
                f"🎲 Редкость: {rarity.capitalize()}\n"
                f"🎖️ Очки: {points}\n\n"
                
                f"🔄 Осталось прокруток: {spins - 1 if spins > 0 else 0}"
            ),
            parse_mode="Markdown"
        )

    conn.close()


@cardreceive_router.message(Command("giveadmcard"))
async def give_admin_card(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (OWNER_ID,))
    selected_universe = cursor.fetchone()[0]

    cursor.execute(f"SELECT card_id, name, rarity, photo_id, points FROM [{selected_universe}]")
    cards = cursor.fetchall()

    if not cards:
        await message.answer(f"Нет карт во вселенной {selected_universe.capitalize()}.")
        conn.close()
        return

    card = get_random_card(cards)
    card_id, name, rarity, photo_id, points = card

    cursor.execute("""
        INSERT INTO user_cards (user_id, card_id, universe, quantity)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id, card_id, universe) DO UPDATE SET quantity = quantity + 1
    """, (message.from_user.id, card_id, selected_universe))
    conn.commit()
    conn.close()

    await message.answer_photo(
        photo=photo_id,
        caption=(f"Карта «*{name}*» добавлена администратору."),
        parse_mode="Markdown"
    )
