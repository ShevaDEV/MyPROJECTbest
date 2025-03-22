import os
import aiosqlite
import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import OWNER_ID
from handlers.cardshand.callbackcards import OwnerRarityCallback, EditCardCallback, AdminPaginationCallback
from kbds.inlinecards import rarity_keyboard_for_owner, admin_pagination_keyboard

admincards_router = Router()

@admincards_router.message(Command("view_cards"))
@admincards_router.message(F.text == "Карты в базе")
async def admin_view_cards(message: types.Message):
    """📌 Команда для просмотра вселенных."""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ У вас нет прав.")
        return

    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT universe_id, name FROM universes WHERE enabled = 1") as cursor:
            universes = await cursor.fetchall()

    if not universes:
        await message.answer("📂 Нет доступных вселенных.")
        return

    builder = InlineKeyboardBuilder()
    for universe_id, universe_name in universes:
        builder.row(InlineKeyboardButton(text=universe_name, callback_data=f"view_{universe_id}"))

    await message.answer("🌌 Выберите вселенную:", reply_markup=builder.as_markup())

@admincards_router.callback_query(lambda c: c.data.startswith("view_"))
async def view_universe(callback: types.CallbackQuery):
    """🔹 Отображает редкости карт для выбранной вселенной."""
    universe_id = callback.data.split("_", 1)[1]

    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT enabled, name FROM universes WHERE universe_id = ?", (universe_id,)) as cursor:
            result = await cursor.fetchone()

    if not result or result[0] != 1:
        await callback.answer("❌ Выбранная вселенная недоступна.")
        return

    universe_name = result[1]
    rarity_kb = rarity_keyboard_for_owner(universe_id)

    await callback.message.answer(f"🎴 Выберите редкость карт из вселенной *{universe_name}*:", reply_markup=rarity_kb, parse_mode="Markdown")
    await callback.answer()

@admincards_router.callback_query(OwnerRarityCallback.filter())
async def rarity_selected(callback: types.CallbackQuery, callback_data: OwnerRarityCallback, state: FSMContext):
    """🔹 Загружает карты с выбранной редкостью."""
    universe = callback_data.universe
    rarity_type = callback_data.rarity_type

    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute(f"""
            SELECT card_id, name, photo_path, rarity, attack, hp, points
            FROM [{universe}]
            WHERE rarity = ?
        """, (rarity_type,)) as cursor:
            cards = await cursor.fetchall()

    if not cards:
        await callback.message.answer(f"📭 В этой вселенной нет карт с редкостью *{rarity_type.capitalize()}*.", parse_mode="Markdown")
        return

    await state.update_data(admin_cards=cards, universe=universe)

    card_id, name, photo_path, rarity, attack, hp, points = cards[0]
    caption = (
        f"🆔 ID: `{card_id}`\n"
        f"🏷️ Имя: *{name}*\n"
        f"🎲 Редкость: *{rarity.capitalize()}*\n"
        f"⚔️ Атака: `{attack}`\n"
        f"❤️ Здоровье: `{hp}`\n"
        f"💎 Очки: `{points}`\n"
    )

    pagination_markup = combine_pagination_and_edit_buttons(rarity, 0, len(cards), card_id, universe)

    if not os.path.isfile(photo_path):
        await callback.message.answer(f"❌ Ошибка: изображение карты (ID: `{card_id}`) не найдено.", parse_mode="Markdown")
        return

    photo_file = await asyncio.to_thread(FSInputFile, photo_path)

    await callback.message.answer_photo(photo=photo_file, caption=caption, reply_markup=pagination_markup, parse_mode="Markdown")
    await callback.answer()

@admincards_router.callback_query(AdminPaginationCallback.filter())
async def paginate_cards(callback: types.CallbackQuery, callback_data: AdminPaginationCallback, state: FSMContext):
    """🔹 Переключает страницы карт (пагинация)."""
    rarity_type = callback_data.rarity_type
    index = callback_data.index

    data = await state.get_data()
    cards = data.get("admin_cards")
    universe = data.get("universe")

    if not cards:
        await callback.answer("❌ Ошибка: данные для пагинации не найдены.", show_alert=True)
        return

    index = index % len(cards)
    card_id, name, photo_path, rarity, attack, hp, points = cards[index]

    caption = (
        f"🆔 ID: `{card_id}`\n"
        f"🏷️ Имя: *{name}*\n"
        f"🎲 Редкость: *{rarity.capitalize()}*\n"
        f"⚔️ Атака: `{attack}`\n"
        f"❤️ Здоровье: `{hp}`\n"
        f"💎 Очки: `{points}`\n"
    )

    pagination_markup = combine_pagination_and_edit_buttons(rarity_type, index, len(cards), card_id, universe)

    if not os.path.isfile(photo_path):
        await callback.message.answer(f"❌ Ошибка: изображение карты (ID: `{card_id}`) не найдено.", parse_mode="Markdown")
        return

    photo_file = await asyncio.to_thread(FSInputFile, photo_path)

    await callback.message.edit_media(
        media=types.InputMediaPhoto(media=photo_file, caption=caption, parse_mode="Markdown"),
        reply_markup=pagination_markup
    )
    await callback.answer()

def combine_pagination_and_edit_buttons(rarity, index, total, card_id, universe):
    """
    🔹 Генерирует клавиатуру с кнопками пагинации и редактирования.
    """
    builder = InlineKeyboardBuilder()

    if total > 1:
        builder.row(
            InlineKeyboardButton(text="⬅️", callback_data=AdminPaginationCallback(rarity_type=rarity, index=(index - 1) % total).pack()),
            InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
            InlineKeyboardButton(text="➡️", callback_data=AdminPaginationCallback(rarity_type=rarity, index=(index + 1) % total).pack())
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Редкость", callback_data=EditCardCallback(action="edit_rarity", card_id=card_id, universe=universe).pack()),
        InlineKeyboardButton(text="✏️ Очки", callback_data=EditCardCallback(action="edit_points", card_id=card_id, universe=universe).pack()),
        InlineKeyboardButton(text="❌ Карту", callback_data=EditCardCallback(action="delete", card_id=card_id, universe=universe).pack())
    )

    return builder.as_markup()
