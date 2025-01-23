from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto
from handlers.cardshand.callbackcards import RarityCallback, ReturnCallback
from kbds.inlinecards import rarity_keyboard_for_user, pagination_keyboard
import sqlite3
import os

cardsall_router = Router()

@cardsall_router.message(Command("cards"))
@cardsall_router.message(F.text.lower() == "мои карты")
@cardsall_router.callback_query(lambda c: c.data == "view_cards")
async def show_user_cards(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id if isinstance(event, types.Message) else event.message.chat.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Получаем выбранную вселенную пользователя
    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    selected_universe = cursor.fetchone()

    if not selected_universe or not selected_universe[0]:
        await (event.answer if isinstance(event, types.CallbackQuery) else event.reply)(
            "Вы не выбрали вселенную. Используйте команду /selectuniverse для выбора."
        )
        conn.close()
        return

    selected_universe = selected_universe[0]

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

    # Если карт у пользователя нет
    if not user_cards:
        await (event.answer if isinstance(event, types.CallbackQuery) else event.reply)(
            f"В выбранной вселенной '{selected_universe.capitalize()}' у вас пока нет карт."
        )
        return

    # Формируем клавиатуру с кнопками редкостей
    keyboard = rarity_keyboard_for_user(user_cards=user_cards, total_cards=total_cards, universe=selected_universe)

    # Формируем сообщение с указанием вселенной
    message_text = f"Какие карты из вселенной {selected_universe.capitalize()} хотите посмотреть?"

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(message_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await event.reply(message_text, reply_markup=keyboard, parse_mode="Markdown")


@cardsall_router.callback_query(RarityCallback.filter())
async def show_cards_by_rarity(callback: types.CallbackQuery, callback_data: RarityCallback):
    user_id = callback.from_user.id
    rarity = callback_data.rarity_type
    universe = callback_data.universe

    # Проверка валидности редкости
    valid_rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]
    if rarity not in valid_rarities:
        await callback.answer("Неверный тип редкости.", show_alert=True)
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Получаем карты указанной редкости для выбранной вселенной
    cursor.execute(f"""
    SELECT c.card_id, c.name, c.photo_path, c.rarity, c.points
    FROM user_cards uc
    JOIN [{universe}] c ON uc.card_id = c.card_id
    WHERE uc.user_id = ? AND c.rarity = ?
    """, (user_id, rarity))

    cards = cursor.fetchall()
    conn.close()

    if not cards:
        # Если карт нет, отображаем сообщение с кнопкой "Вернуться"
        await callback.message.edit_text(
            f"У вас нет карт редкости: {rarity.capitalize()}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Вернуться", callback_data=ReturnCallback(action="to_categories").pack())]
            ])
        )
        return

    # Если карты есть, отправляем данные первой карты
    card_id, name, photo_path, rarity, points = cards[0]

    # Проверяем существование изображения
    if not os.path.isfile(photo_path):
        await callback.message.edit_text(
            f"Ошибка: файл изображения для карты '{name}' не найден.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Вернуться", callback_data=ReturnCallback(action="to_categories").pack())]
            ])
        )
        return

    # Создаем сообщение о карте
    media = InputMediaPhoto(
        media=FSInputFile(photo_path),
    caption = (
        f"🃏 *Карта*: «*{name}*»\n"
        f"🎲 *Редкость*: *{rarity.capitalize()}*\n"
        f"💎 *Очки*: *{points}*"
    ),
        parse_mode="Markdown"
    )

    # Создаем клавиатуру для пагинации
    reply_markup = pagination_keyboard(rarity=rarity, index=0, total=len(cards), include_return=True)

    await callback.message.edit_media(
        media=media,
        reply_markup=reply_markup
    )


@cardsall_router.callback_query(ReturnCallback.filter(F.action == "to_categories"))
async def return_to_categories(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Получаем выбранную вселенную пользователя
    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    selected_universe = cursor.fetchone()

    if not selected_universe or not selected_universe[0]:
        await callback.message.delete()
        await callback.message.answer("Вы не выбрали вселенную!")
        conn.close()
        return

    selected_universe = selected_universe[0]

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
    keyboard = rarity_keyboard_for_user(user_cards=user_cards, total_cards=total_cards, universe=selected_universe)

    # Формируем сообщение с указанием вселенной
    message_text = f"Какие карты из вселенной {selected_universe.capitalize()} хотите посмотреть?"

    # Удаляем сообщение с карточкой и отправляем новое
    await callback.message.delete()
    await callback.message.answer(message_text, reply_markup=keyboard, parse_mode="Markdown")
