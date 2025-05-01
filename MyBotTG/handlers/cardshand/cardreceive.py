from aiogram import Router, types, F
from aiogram.filters import Command
from datetime import datetime, timedelta
from random import choices
import os
from aiogram.types import FSInputFile
from config import OWNER_ID
from dabase.database import db_instance  # ✅ Используем db_instance

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


def get_random_card(cards: list) -> dict:
    """Выбирает случайную карту с учетом редкости."""
    rarities = [card[2] for card in cards]  # ✅ Теперь берём редкость из tuple
    weights = [RARITY_WEIGHTS.get(rarity, 1) for rarity in rarities]
    return choices(cards, weights=weights, k=1)[0]


async def check_cooldown(user_id: int) -> bool:
    """Проверяет, действует ли кулдаун."""
    db = await db_instance.get_connection()
    async with db.execute("SELECT last_card_time FROM users WHERE user_id = ?", (user_id,)) as cursor:
        result = await cursor.fetchone()

    if result and result[0]:  # ✅ Теперь корректно
        last_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return datetime.now() - last_time < timedelta(hours=CARD_RECEIVE_COOLDOWN)

    return False


@cardreceive_router.message(Command("card"))
@cardreceive_router.message(F.text.lower() == "дай карту")
async def give_card(message: types.Message):
    user_id = message.from_user.id
    db = await db_instance.get_connection()

    async with db.execute("SELECT spins FROM users WHERE user_id = ?", (user_id,)) as cursor:
        result = await cursor.fetchone()

    spins = result[0] if result else 0  # ✅ Теперь корректно

    if spins > 0:
        await db.execute("UPDATE users SET spins = spins - 1 WHERE user_id = ?", (user_id,))
        await db.commit()
    else:
        if await check_cooldown(user_id):
            async with db.execute("SELECT last_card_time FROM users WHERE user_id = ?", (user_id,)) as cursor:
                result = await cursor.fetchone()

            last_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S") if result else datetime.now()
            next_available_time = last_time + timedelta(hours=CARD_RECEIVE_COOLDOWN)
            time_remaining = next_available_time - datetime.now()

            hours, remainder = divmod(time_remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            await message.answer(
                f"Вы уже получали карту! Следующая будет доступна через {hours} час(а) и {minutes} минут(ы)."
            )
            return

    async with db.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,)) as cursor:
        universe_result = await cursor.fetchone()

    if not universe_result or not universe_result[0]:  # ✅ Исправлено
        await message.answer("Вы не выбрали вселенную. Используйте /select_universe для выбора.")
        return

    selected_universe = universe_result[0]  # ✅ Достаём значение из tuple

    async with db.execute(f"SELECT card_id, name, rarity, photo_path, points FROM [{selected_universe}]") as cursor:
        cards = await cursor.fetchall()

    if not cards:
        await message.answer(f"В базе данных {selected_universe.capitalize()} нет карт.")
        return

    card = get_random_card(cards)

    if not os.path.isfile(card[3]):  # ✅ Берём путь к фото из tuple
        await message.answer(f"Ошибка: файл изображения не найден по пути {card[3]}.")
        return

    async with db.execute("""
        SELECT quantity FROM user_cards WHERE user_id = ? AND card_id = ? AND universe_id = ?
    """, (user_id, card[0], selected_universe)) as cursor:
        result = await cursor.fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if result:
        await db.execute("UPDATE users SET total_points = total_points + ? WHERE user_id = ?", (card[4], user_id))
        await db.execute("UPDATE users SET last_card_time = ? WHERE user_id = ?", (now, user_id))
    else:
        await db.execute("""
            INSERT INTO user_cards (user_id, card_id, universe_id, quantity)
            VALUES (?, ?, ?, 1)
        """, (user_id, card[0], selected_universe))

        await db.execute("UPDATE users SET total_points = total_points + ? WHERE user_id = ?", (card[4], user_id))
        await db.execute("UPDATE users SET last_card_time = ? WHERE user_id = ?", (now, user_id))

    await db.commit()

    caption = (
        f"🎉 Ваша коллекция пополнилась карточкой «*{card[1]}*»!\n\n"
        f"🎲 Редкость: {card[2].capitalize()}\n"
        f"💎 Очки: {card[4]}\n\n"
        f"🔄 Осталось прокруток: {spins - 1 if spins > 0 else 0}"
    ) if not result else (
        f"🎉 Вам выпала повторная карточка «*{card[1]}*»!\n"
        f"🎲 Редкость: {card[2].capitalize()}\n"
        f"💎 Очки: +{card[4]} добавлено к вашему счёту.\n\n"
        f"🔄 Осталось прокруток: {spins - 1 if spins > 0 else 0}"
    )

    await message.answer_photo(
        photo=FSInputFile(card[3]),
        caption=caption,
        parse_mode="Markdown"
    )


@cardreceive_router.message(Command("giveadmcard"))
async def give_admin_card(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("🚫 У вас нет прав на использование этой команды.")
        return

    db = await db_instance.get_connection()

    async with db.execute("SELECT selected_universe FROM users WHERE user_id = ?", (OWNER_ID,)) as cursor:
        selected_universe = (await cursor.fetchone())[0]

    async with db.execute(f"SELECT card_id, name, rarity, photo_path, points FROM [{selected_universe}]") as cursor:
        cards = await cursor.fetchall()

    if not cards:
        await message.answer(f"⚠ Нет карт во вселенной {selected_universe.capitalize()}.")
        return

    card = get_random_card(cards)

    await db.execute("""
        INSERT INTO user_cards (user_id, card_id, universe_id, quantity)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id, card_id, universe_id) DO UPDATE SET quantity = quantity + 1
    """, (message.from_user.id, card[0], selected_universe))

    await db.commit()

    await message.answer_photo(
        photo=FSInputFile(card[3]),
        caption=(
            f"✅ *Администратор получил карту!*\n\n"
            f"🃏 *Карта:* {card[1]}\n"
            f"🎲 *Редкость:* {card[2].capitalize()}\n"
            f"💎 *Очки:* {card[4]}\n\n"
            f"📦 *Добавлена в коллекцию!*"
        ),
        parse_mode="Markdown"
    )
