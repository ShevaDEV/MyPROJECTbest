from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto
from handlers.cardshand.callbackcards import RarityCallback, ReturnCallback
from kbds.inlinecards import rarity_keyboard_for_user, pagination_keyboard
import sqlite3
import os

cardsall_router = Router()

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы в Markdown."""
    special_chars = "_*[]()~`>#+-=|{}.!\\"
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

@cardsall_router.message(Command("cards"))
@cardsall_router.message(F.text.lower() == "мои карты")
@cardsall_router.callback_query(lambda c: c.data == "view_cards")
async def show_user_cards(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id if isinstance(event, types.Message) else event.message.chat.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    selected_universe = cursor.fetchone()

    if not selected_universe or not selected_universe[0]:
        await (event.answer if isinstance(event, types.CallbackQuery) else event.reply)(
            "Вы не выбрали вселенную. Используйте команду /select_universe для выбора."
        )
        conn.close()
        return

    cursor.execute("SELECT name FROM universes WHERE universe_id = ?", (selected_universe[0],))
    universe_name = cursor.fetchone()
    if not universe_name:
        await event.reply("Ошибка: Вселенная не найдена в базе данных.")
        conn.close()
        return

    universe_name = universe_name[0]  # Используем правильное название

    cursor.execute(f"""
    SELECT c.rarity, COUNT(uc.card_id)
    FROM user_cards uc
    JOIN [{selected_universe[0]}] c ON uc.card_id = c.card_id
    WHERE uc.user_id = ?
    GROUP BY c.rarity
    """, (user_id,))
    user_cards = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute(f"""
    SELECT rarity, COUNT(card_id)
    FROM [{selected_universe[0]}]
    GROUP BY rarity
    """)
    total_cards = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    if not user_cards:
        await (event.answer if isinstance(event, types.CallbackQuery) else event.reply)(
            f"В выбранной вселенной '{escape_markdown(universe_name)}' у вас пока нет карт.",
            parse_mode="Markdown"
        )
        return

    keyboard = rarity_keyboard_for_user(user_cards=user_cards, total_cards=total_cards, universe=selected_universe[0])
    message_text = f"Какие карты из вселенной {escape_markdown(universe_name)} хотите посмотреть?"

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(message_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await event.reply(message_text, reply_markup=keyboard, parse_mode="Markdown")


@cardsall_router.callback_query(RarityCallback.filter())
async def show_cards_by_rarity(callback: types.CallbackQuery, callback_data: RarityCallback):
    user_id = callback.from_user.id
    rarity = callback_data.rarity_type
    universe = callback_data.universe

    valid_rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]
    if rarity not in valid_rarities:
        await callback.answer("Неверный тип редкости.", show_alert=True)
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute(f"""
    SELECT c.card_id, c.name, c.photo_path, c.rarity, c.points
    FROM user_cards uc
    JOIN [{universe}] c ON uc.card_id = c.card_id
    WHERE uc.user_id = ? AND c.rarity = ?
    """, (user_id, rarity))

    cards = cursor.fetchall()
    conn.close()

    if not cards:
        await callback.message.edit_text(
            f"У вас нет карт редкости: {escape_markdown(rarity.capitalize())}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Вернуться", callback_data=ReturnCallback(action="to_categories").pack())]
            ]),
            parse_mode="Markdown"
        )
        return

    card_id, name, photo_path, rarity, points = cards[0]

    if not os.path.isfile(photo_path):
        await callback.message.edit_text(
            f"Ошибка: файл изображения для карты '{escape_markdown(name)}' не найден.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Вернуться", callback_data=ReturnCallback(action="to_categories").pack())]
            ]),
            parse_mode="Markdown"
        )
        return

    media = InputMediaPhoto(
        media=FSInputFile(photo_path),
        caption=(
            f"🃏 *Карта*: *{escape_markdown(name)}*\n"
            f"🎲 *Редкость*: *{escape_markdown(rarity.capitalize())}*\n"
            f"💎 *Очки*: *{points}*"
        ),
        parse_mode="Markdown"
    )

    reply_markup = pagination_keyboard(rarity=rarity, index=0, total=len(cards), include_return=True)

    await callback.message.edit_media(media=media, reply_markup=reply_markup)


@cardsall_router.callback_query(ReturnCallback.filter(F.action == "to_categories"))
async def return_to_categories(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Используем конструкцию with для автоматического закрытия соединения
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
        selected_universe = cursor.fetchone()

        if not selected_universe or not selected_universe[0]:
            await callback.message.delete()
            await callback.message.answer("Вы не выбрали вселенную!")
            return

        selected_universe = selected_universe[0]

        cursor.execute(f"""
        SELECT c.rarity, COUNT(uc.card_id)
        FROM user_cards uc
        JOIN [{selected_universe}] c ON uc.card_id = c.card_id
        WHERE uc.user_id = ?
        GROUP BY c.rarity
        """, (user_id,))
        user_cards = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(f"""
        SELECT rarity, COUNT(card_id)
        FROM [{selected_universe}]
        GROUP BY rarity
        """)
        total_cards = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT name FROM universes WHERE universe_id = ?", (selected_universe,))
        universe_name = cursor.fetchone()
        if not universe_name:
            await callback.message.answer("Ошибка: Вселенная не найдена в базе данных.")
            return

        universe_name = universe_name[0]

        keyboard = rarity_keyboard_for_user(user_cards=user_cards, total_cards=total_cards, universe=selected_universe)
        message_text = f"Какие карты из вселенной {escape_markdown(universe_name)} хотите посмотреть?"

        await callback.message.delete()
        await callback.message.answer(message_text, reply_markup=keyboard, parse_mode="Markdown")

