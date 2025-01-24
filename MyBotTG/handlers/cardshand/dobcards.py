import os
import sqlite3
import random
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from config import OWNER_ID, AVAILABLE_UNIVERSES

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

# Генерация инлайн-клавиатуры для выбора вселенной
def create_universe_inline_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора вселенной."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=universe.capitalize(), callback_data=f"universe_{universe}")]
            for universe in AVAILABLE_UNIVERSES
        ]
    )

@dobcards_router.message(Command("addcard"))
@dobcards_router.message(F.text.lower() == "добавить карту")
async def add_card(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    await message.answer(
        "Выберите вселенную для добавления карты:",
        reply_markup=create_universe_inline_keyboard()
    )
    await state.set_state(AddCardState.waiting_for_universe)

@dobcards_router.callback_query(F.data.startswith("universe_"))
async def card_universe_received(callback: types.CallbackQuery, state: FSMContext):
    universe = callback.data.split("_")[1]

    if universe not in AVAILABLE_UNIVERSES:
        await callback.answer("Выбрана недопустимая вселенная.", show_alert=True)
        return

    await state.update_data(universe=universe)
    await callback.message.edit_text("Отправьте фото карты для загрузки.")
    await state.set_state(AddCardState.waiting_for_photo)

@dobcards_router.message(AddCardState.waiting_for_photo, F.photo)
async def card_photo_received(message: types.Message, state: FSMContext):
    universe = (await state.get_data())["universe"]
    photo = message.photo[-1]

    # Сохраняем изображение в локальную папку
    folder_path = f"images/{universe}"
    os.makedirs(folder_path, exist_ok=True)  # Создаем папку, если она не существует
    file_path = f"{folder_path}/{photo.file_unique_id}.jpg"

    # Получаем файл и загружаем его
    file = await message.bot.get_file(photo.file_id)
    await message.bot.download_file(file.file_path, destination=file_path)

    await state.update_data(photo_path=file_path)
    await message.answer("Введите название карты.")
    await state.set_state(AddCardState.waiting_for_name)

@dobcards_router.message(AddCardState.waiting_for_name)
async def card_name_received(message: types.Message, state: FSMContext):
    name = message.text
    await state.update_data(name=name)

    await message.answer(
        "Введите редкость карты. Допустимые значения:\n"
        "обычная, редкая, эпическая, легендарная, мифическая.",
        parse_mode="Markdown"
    )
    await state.set_state(AddCardState.waiting_for_rarity)

@dobcards_router.message(AddCardState.waiting_for_rarity)
async def card_rarity_received(message: types.Message, state: FSMContext):
    rarity = message.text.lower()

    if rarity not in RARITY_RANGES:
        await message.answer("Пожалуйста, выберите одну из предложенных редкостей.")
        return

    # Получаем данные из состояния
    card_data = await state.get_data()
    photo_path = card_data["photo_path"]
    name = card_data["name"]
    universe = card_data["universe"]

    # Проверяем существование карты
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT 1 FROM {universe} WHERE name = ?", (name,))
    if cursor.fetchone():
        await message.answer(f"Карта с именем '{name}' уже существует в вселенной '{universe.capitalize()}'.")
        conn.close()
        await state.clear()
        return

    # Генерация характеристик карты
    attack = random.randint(*RARITY_RANGES[rarity]["attack"])
    hp = random.randint(*RARITY_RANGES[rarity]["hp"])

    # Генерация поинтов с окончанием 00 или 50
    points_range = range(RARITY_POINTS[rarity][0], RARITY_POINTS[rarity][1] + 1, 50)
    points = random.choice(points_range)

    # Сохраняем карту в базу данных
    cursor.execute(f"""
    INSERT INTO {universe} (name, photo_path, rarity, attack, hp, points)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (name, photo_path, rarity, attack, hp, points))
    conn.commit()
    conn.close()

    await message.answer(
        f"Карта '{name}' успешно добавлена в таблицу '{universe.capitalize()}'!\n\n"
        f"📋 Характеристики:\n"
        f"🎲 Редкость: {rarity.capitalize()}\n"
        f"⚔️ Атака: {attack}\n"
        f"❤️ Здоровье: {hp}\n"
        f"🎖️ Очки: {points} points"
    )
    await state.clear()
