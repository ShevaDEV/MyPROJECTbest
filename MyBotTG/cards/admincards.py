import sqlite3
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import os
import logging
from config import OWNER_ID
from handlers.cardshand.callbackcards import OwnerRarityCallback, EditCardCallback, AdminPaginationCallback
from kbds.inlinecards import rarity_keyboard_for_owner, admin_pagination_keyboard

admincards_router = Router()

# Обработчик нажатия на кнопку "Карты в базе" для владельца
@admincards_router.message(Command("view_cards"))
@admincards_router.message(F.text == "Карты в базе")
async def admin_view_cards(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    logging.info("Отправлено сообщение для выбора вселенной.")
    
    # Подключаемся к базе данных и получаем доступные вселенные
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT universe_id, name FROM universes WHERE enabled = 1")
    universes = cursor.fetchall()
    conn.close()

    if not universes:
        await message.answer("Нет доступных вселенных.")
        return

    builder = InlineKeyboardBuilder()
    for universe_id, universe_name in universes:
        # Теперь имя вселенной будет отображаться как в базе данных, без изменений
        builder.row(InlineKeyboardButton(text=universe_name, callback_data=f"view_{universe_id}"))
    
    await message.answer("Выберите вселенную:", reply_markup=builder.as_markup())

# Обработчик для выбора вселенной
@admincards_router.callback_query(lambda c: c.data.startswith("view_"))
async def view_universe(callback: types.CallbackQuery):
    universe_id = callback.data.split("_", 1)[1]  # Получаем id вселенной, теперь используем full id (например, "star_wars")

    # Логируем выбранную вселенную
    logging.info(f"Попытка выбрать вселенную: {universe_id}")

    # Проверяем, существует ли вселенная в базе данных
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT enabled, name FROM universes WHERE universe_id = ?", (universe_id,))
    result = cursor.fetchone()
    conn.close()

    if result is None or result[0] != 1:
        await callback.answer("Выбранная вселенная недоступна.")
        logging.error(f"Вселенная {universe_id} не найдена или не доступна в базе данных.")
        return

    universe_name = result[1]  # Получаем полное имя вселенной, например, "Star Wars"

    # Если все проверки пройдены, отправляем клавиатуру с редкостями
    rarity_kb = rarity_keyboard_for_owner(universe_id)
    await callback.message.answer(f"Выберите редкость карт из вселенной {universe_name}:", reply_markup=rarity_kb)
    await callback.answer()


# Добавляем обработчик для редкости
@admincards_router.callback_query(OwnerRarityCallback.filter())
async def rarity_selected(callback: types.CallbackQuery, callback_data: OwnerRarityCallback, state: FSMContext):
    universe = callback_data.universe
    rarity_type = callback_data.rarity_type

    # Получаем карты из базы данных
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        SELECT card_id, name, photo_path, rarity, attack, hp, points
        FROM [{universe}]
        WHERE rarity = ?
        """, (rarity_type,))
        cards = cursor.fetchall()

    if not cards:
        await callback.message.answer(f"В этой вселенной нет карт с редкостью {rarity_type.capitalize()}.")
        await callback.answer()
        return

    # Сохраняем данные в FSMContext
    await state.update_data(admin_cards=cards, universe=universe)

    # Отправляем первую карту
    card_id, name, photo_path, rarity, attack, hp, points = cards[0]
    caption = (
        f"🆔 ID: {card_id}\n"
        f"🏷️ Имя: {name}\n"
        f"🎲 Редкость: {rarity.capitalize()}\n"
        f"⚔️ Атака: {attack}\n"
        f"❤️ Здоровье: {hp}\n"
        f"💎 Очки: {points}\n"
    )
    pagination_markup = combine_pagination_and_edit_buttons(
        rarity=rarity_type, index=0, total=len(cards), card_id=card_id, universe=universe
    )

    # Проверяем существование изображения
    if not os.path.isfile(photo_path):
        await callback.message.answer(f"Ошибка: изображение карты (ID: {card_id}) не найдено.")
        await callback.answer()
        return

    photo_file = FSInputFile(photo_path)
    await callback.message.answer_photo(
        photo=photo_file,
        caption=caption,
        reply_markup=pagination_markup
    )
    await callback.answer()

# Обработчик для пагинации
@admincards_router.callback_query(AdminPaginationCallback.filter())
async def paginate_cards(callback: types.CallbackQuery, callback_data: AdminPaginationCallback, state: FSMContext):
    rarity_type = callback_data.rarity_type
    index = callback_data.index

    # Получаем данные из FSMContext
    data = await state.get_data()
    cards = data.get("admin_cards")
    universe = data.get("universe")

    if not cards:
        await callback.answer("Данные для пагинации не найдены.", show_alert=True)
        return

    # Корректируем индекс
    index = index % len(cards)

    # Получаем данные для текущей карты
    card_id, name, photo_path, rarity, attack, hp, points = cards[index]

    # Формируем описание карты
    caption = (
        f"🆔 ID: {card_id}\n"
        f"🏷️ Имя: {name}\n"
        f"🎲 Редкость: {rarity.capitalize()}\n"
        f"⚔️ Атака: {attack}\n"
        f"❤️ Здоровье: {hp}\n"
        f"💎 Очки: {points}\n"
    )

    # Кнопки пагинации и редактирования
    pagination_markup = combine_pagination_and_edit_buttons(
        rarity=rarity_type, index=index, total=len(cards), card_id=card_id, universe=universe
    )

    # Проверяем существование изображения
    if not os.path.isfile(photo_path):
        await callback.message.answer(f"Ошибка: изображение карты (ID: {card_id}) не найдено.")
        await callback.answer()
        return

    photo_file = FSInputFile(photo_path)
    await callback.message.edit_media(
        media=types.InputMediaPhoto(media=photo_file, caption=caption),
        reply_markup=pagination_markup
    )

    await callback.answer()

def combine_pagination_and_edit_buttons(rarity, index, total, card_id, universe):
    """
    Объединяет кнопки пагинации и редактирования в одну клавиатуру.
    :param rarity: Редкость карт.
    :param index: Индекс текущей карты.
    :param total: Общее количество карт.
    :param card_id: ID текущей карты.
    :param universe: Вселенная карт.
    :return: InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки пагинации
    if total > 1:
        builder.row(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AdminPaginationCallback(rarity_type=rarity, index=(index - 1) % total).pack()
            ),
            InlineKeyboardButton(
                text=f"{index + 1}/{total}",
                callback_data="noop"  # Неприменяемая кнопка, отображающая текущий счётчик
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=AdminPaginationCallback(rarity_type=rarity, index=(index + 1) % total).pack()
            )
        )

    # Добавляем кнопки редактирования
    builder.row(
        InlineKeyboardButton(
            text="✏️ Редкость",
            callback_data=EditCardCallback(action="edit_rarity", card_id=card_id, universe=universe).pack()
        ),
        InlineKeyboardButton(
            text="✏️ Очки",
            callback_data=EditCardCallback(action="edit_points", card_id=card_id, universe=universe).pack()
        ),
        InlineKeyboardButton(
            text="❌ Карту",
            callback_data=EditCardCallback(action="delete", card_id=card_id, universe=universe).pack()
        )
    )

    return builder.as_markup()
