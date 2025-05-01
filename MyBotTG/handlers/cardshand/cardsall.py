from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto
from handlers.cardshand.callbackcards import RarityCallback, ReturnCallback
from kbds.inlinecards import rarity_keyboard_for_user, pagination_keyboard
import os
from dabase.database import db_instance  # Используем db_instance

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
    db = await db_instance.get_connection()

    async with db.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,)) as cursor:
        selected_universe = await cursor.fetchone()

    if not selected_universe or not selected_universe[0]:
        await (event.answer if isinstance(event, types.CallbackQuery) else event.reply)(
            "Вы не выбрали вселенную. Используйте команду /select_universe для выбора."
        )
        return

    universe = selected_universe[0]

    async with db.execute("SELECT name FROM universes WHERE universe_id = ?", (universe,)) as cursor:
        universe_name = await cursor.fetchone()

    if not universe_name or not universe_name[0]:
        await (event.reply if isinstance(event, types.Message) else event.message.edit_text)(
            "Ошибка: Вселенная не найдена в базе данных."
        )
        return

    universe_name = universe_name[0]

    async with db.execute(f"""
        SELECT c.rarity, COUNT(uc.card_id)
        FROM user_cards uc
        JOIN [{universe}] c ON uc.card_id = c.card_id
        WHERE uc.user_id = ?
        GROUP BY c.rarity
    """, (user_id,)) as cursor:
        user_cards = {row[0]: row[1] for row in await cursor.fetchall()}

    async with db.execute(f"""
        SELECT rarity, COUNT(card_id)
        FROM [{universe}]
        GROUP BY rarity
    """) as cursor:
        total_cards = {row[0]: row[1] for row in await cursor.fetchall()}

    if not user_cards:
        await (event.answer if isinstance(event, types.CallbackQuery) else event.reply)(
            f"В выбранной вселенной '{escape_markdown(universe_name)}' у вас пока нет карт.",
            parse_mode="Markdown"
        )
        return

    keyboard = rarity_keyboard_for_user(user_cards=user_cards, total_cards=total_cards, universe=universe)
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
    db = await db_instance.get_connection()

    valid_rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]
    if rarity not in valid_rarities:
        await callback.answer("Неверный тип редкости.", show_alert=True)
        return

    async with db.execute(f"""
        SELECT c.card_id, c.name, c.photo_path, c.rarity, c.points
        FROM user_cards uc
        JOIN [{universe}] c ON uc.card_id = c.card_id
        WHERE uc.user_id = ? AND c.rarity = ?
    """, (user_id, rarity)) as cursor:
        cards = await cursor.fetchall()

    if not cards:
        await callback.message.edit_text(
            f"У вас нет карт редкости: {escape_markdown(rarity.capitalize())}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Вернуться", callback_data=ReturnCallback(action="to_categories").pack())]
            ]),
            parse_mode="Markdown"
        )
        return

    card = cards[0]
    card_id, name, photo_path, rarity, points = card

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
    db = await db_instance.get_connection()

    async with db.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,)) as cursor:
        selected_universe = await cursor.fetchone()

    if not selected_universe or not selected_universe[0]:
        await callback.message.delete()
        await callback.message.answer("Вы не выбрали вселенную!")
        return

    universe = selected_universe[0]

    async with db.execute(f"""
        SELECT c.rarity, COUNT(uc.card_id)
        FROM user_cards uc
        JOIN [{universe}] c ON uc.card_id = c.card_id
        WHERE uc.user_id = ?
        GROUP BY c.rarity
    """, (user_id,)) as cursor:
        user_cards = {row[0]: row[1] for row in await cursor.fetchall()}

    async with db.execute(f"""
        SELECT rarity, COUNT(card_id)
        FROM [{universe}]
        GROUP BY rarity
    """) as cursor:
        total_cards = {row[0]: row[1] for row in await cursor.fetchall()}

    async with db.execute("SELECT name FROM universes WHERE universe_id = ?", (universe,)) as cursor:
        universe_name = await cursor.fetchone()

    if not universe_name or not universe_name[0]:
        await callback.message.answer("Ошибка: Вселенная не найдена в базе данных.")
        return

    universe_name = universe_name[0]

    keyboard = rarity_keyboard_for_user(user_cards=user_cards, total_cards=total_cards, universe=universe)
    message_text = f"Какие карты из вселенной {escape_markdown(universe_name)} хотите посмотреть?"

    await callback.message.delete()
    await callback.message.answer(message_text, reply_markup=keyboard, parse_mode="Markdown")
