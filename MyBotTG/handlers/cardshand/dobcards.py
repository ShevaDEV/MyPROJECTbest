import os
import sqlite3
import random
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import OWNER_ID  # Убедитесь, что OWNER_ID задан правильно

dobcards_router = Router()

# Диапазоны очков (поинтов) для редкостей
RARITY_POINTS = {
    "обычная": (50, 200),
    "редкая": (350, 550),
    "эпическая": (750, 1050),
    "легендарная": (1350, 1850),
    "мифическая": (2250, 2750),
}

# Диапазоны для атаки и здоровья по редкости
RARITY_RANGES = {
    "обычная": {"attack": (10, 30), "hp": (20, 50)},
    "редкая": {"attack": (30, 50), "hp": (50, 80)},
    "эпическая": {"attack": (50, 80), "hp": (80, 120)},
    "легендарная": {"attack": (80, 120), "hp": (120, 180)},
    "мифическая": {"attack": (120, 180), "hp": (180, 250)},
}

# Состояния для добавления карты
class AddCardState(StatesGroup):
    waiting_for_universe = State()
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_rarity = State()

def get_available_universes() -> list:
    """
    Получает список вселенных из базы данных.
    Каждая вселенная представлена кортежем (universe_id, name).
    Выбираются только те, у которых enabled = 1.
    """
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT universe_id, name FROM universes WHERE enabled = 1")
    universes = cursor.fetchall()
    conn.close()
    return universes

def create_universe_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора вселенной.
    Каждая кнопка: текст — name (капитализированное), callback_data — "universe_<universe_id>".
    """
    universes = get_available_universes()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name.capitalize(), callback_data=f"universe_{universe_id}")]
            for universe_id, name in universes
        ]
    )
    return keyboard

@dobcards_router.message(Command("addcard"))
@dobcards_router.message(F.text.lower() == "добавить карту")
async def add_card(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    kb = create_universe_inline_keyboard()
    if not kb.inline_keyboard:
        await message.answer("Список вселенных пуст или ошибка в базе данных.")
        return

    await message.answer(
        "Выберите вселенную для добавления карты:",
        reply_markup=kb
    )
    await state.set_state(AddCardState.waiting_for_universe)

@dobcards_router.callback_query(F.data.startswith("universe_"))
async def card_universe_received(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем идентификатор вселенной (всё, что после "universe_")
    universe = callback.data.split("_", 1)[1]
    available_universes = [u[0] for u in get_available_universes()]
    if universe not in available_universes:
        await callback.answer("Выбрана недопустимая вселенная.", show_alert=True)
        return

    await state.update_data(universe=universe)
    await callback.message.edit_text("Отправьте фото карты для загрузки.")
    await state.set_state(AddCardState.waiting_for_photo)
    await callback.answer()

@dobcards_router.message(AddCardState.waiting_for_photo, F.photo)
async def card_photo_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    universe = data.get("universe")
    photo = message.photo[-1]

    folder_path = f"images/{universe}"
    os.makedirs(folder_path, exist_ok=True)
    file_path = f"{folder_path}/{photo.file_unique_id}.jpg"

    try:
        file = await message.bot.get_file(photo.file_id)
        await message.bot.download_file(file.file_path, destination=file_path)
    except Exception:
        await message.answer("Ошибка при загрузке фото. Попробуйте еще раз.")
        return

    await state.update_data(photo_path=file_path)
    await message.answer("Введите название карты.")
    await state.set_state(AddCardState.waiting_for_name)

@dobcards_router.message(AddCardState.waiting_for_name)
async def card_name_received(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await message.answer(
        "Введите редкость карты. Допустимые значения:\n"
        "обычная, редкая, эпическая, легендарная, мифическая."
    )
    await state.set_state(AddCardState.waiting_for_rarity)

@dobcards_router.message(AddCardState.waiting_for_rarity)
async def card_rarity_received(message: types.Message, state: FSMContext):
    rarity = message.text.lower().strip()
    if rarity not in RARITY_RANGES:
        await message.answer("Пожалуйста, выберите одну из предложенных редкостей.")
        return

    card_data = await state.get_data()
    photo_path = card_data.get("photo_path")
    name = card_data.get("name")
    universe = card_data.get("universe")

    try:
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM {universe} WHERE name = ?", (name,))
        if cursor.fetchone():
            await message.answer(
                f"Карта с именем '{name}' уже существует в вселенной '{universe.capitalize()}'."
            )
            conn.close()
            await state.clear()
            return

        attack = random.randint(*RARITY_RANGES[rarity]["attack"])
        hp = random.randint(*RARITY_RANGES[rarity]["hp"])
        points_range = range(RARITY_POINTS[rarity][0], RARITY_POINTS[rarity][1] + 1, 50)
        points = random.choice(points_range)

        cursor.execute(f"""
            INSERT INTO {universe} (name, photo_path, rarity, attack, hp, points)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, photo_path, rarity, attack, hp, points))
        conn.commit()
        conn.close()
    except Exception:
        await message.answer("Ошибка при сохранении карты в базу данных.")
        await state.clear()
        return

    await message.answer(
        f"Карта '{name}' успешно добавлена в таблицу '{universe.capitalize()}'!\n\n"
        f"📋 Характеристики:\n"
        f"🎲 Редкость: {rarity.capitalize()}\n"
        f"⚔️ Атака: {attack}\n"
        f"❤️ Здоровье: {hp}\n"
        f"🎖️ Очки: {points} points"
    )
    await state.clear()
