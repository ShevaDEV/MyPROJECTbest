import os
import random
import re
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramNetworkError
from config import OWNER_ID
from dabase.database import db_instance  # ✅ Асинхронная работа с БД

dobcards_router = Router()

# 🔹 Очки для каждой редкости
RARITY_POINTS = {
    "обычная": (50, 200),
    "редкая": (350, 550),
    "эпическая": (750, 1050),
    "легендарная": (1350, 1850),
    "мифическая": (2250, 2750),
}

# 🔹 Атака и Здоровье по редкости
RARITY_RANGES = {
    "обычная": {"attack": (10, 30), "hp": (20, 50)},
    "редкая": {"attack": (30, 50), "hp": (50, 80)},
    "эпическая": {"attack": (50, 80), "hp": (80, 120)},
    "легендарная": {"attack": (80, 120), "hp": (120, 180)},
    "мифическая": {"attack": (120, 180), "hp": (180, 250)},
}

# 🔹 Классы состояний
class AddCardState(StatesGroup):
    waiting_for_universe = State()
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_rarity = State()

# 🔹 Функция экранирования MarkdownV2
def escape_markdown(text: str) -> str:
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(r"([{}])".format(re.escape(escape_chars)), r"\\\1", text)

# 🔹 Получаем вселенные (асинхронно)
async def get_available_universes() -> list:
    db = await db_instance.get_connection()
    async with db.execute("SELECT universe_id, name FROM universes WHERE enabled = 1") as cursor:
        return await cursor.fetchall()

# 🔹 Создаем инлайн-клавиатуру для выбора вселенной
async def create_universe_inline_keyboard() -> InlineKeyboardMarkup:
    universes = await get_available_universes()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name.capitalize(), callback_data=f"universe_{universe_id}")]
            for universe_id, name in universes
        ]
    )

# 🔹 Создаем инлайн-клавиатуру для выбора редкости
def create_rarity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=rar.capitalize(), callback_data=f"rarity_{rar}")]
            for rar in RARITY_RANGES
        ]
    )

# 🔹 Команда "/addcard"
@dobcards_router.message(Command("addcard"))
@dobcards_router.message(F.text.lower() == "добавить карту")
async def add_card(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        await message.answer("🚫 У вас нет прав на использование этой команды.")
        return

    kb = await create_universe_inline_keyboard()
    if not kb.inline_keyboard:
        await message.answer("❌ Ошибка: Список вселенных пуст или ошибка в базе данных.")
        return

    await message.answer("Выберите вселенную для добавления карты:", reply_markup=kb)
    await state.set_state(AddCardState.waiting_for_universe)

# 🔹 Обработка выбора вселенной
@dobcards_router.callback_query(F.data.startswith("universe_"))
async def card_universe_received(callback: types.CallbackQuery, state: FSMContext):
    universe = callback.data.split("_", 1)[1]
    available_universes = [u[0] for u in await get_available_universes()]
    
    if universe not in available_universes:
        await callback.answer("❌ Недопустимая вселенная!", show_alert=True)
        return

    await state.update_data(universe=universe)
    await callback.message.edit_text("📸 Отправьте фото карты для загрузки.")
    await state.set_state(AddCardState.waiting_for_photo)
    await callback.answer()

# 🔹 Обработка фото карты
@dobcards_router.message(AddCardState.waiting_for_photo, F.photo)
async def card_photo_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    universe = data.get("universe")
    photo = message.photo[-1]

    folder_path = f"images/{universe}"
    os.makedirs(folder_path, exist_ok=True)
    file_path = f"{folder_path}/{photo.file_unique_id}.jpg"

    file = await message.bot.get_file(photo.file_id)
    await message.bot.download_file(file.file_path, destination=file_path)

    await state.update_data(photo_path=file_path)
    await message.answer("✏️ Введите название карты.")
    await state.set_state(AddCardState.waiting_for_name)

# 🔹 Обработка имени карты
@dobcards_router.message(AddCardState.waiting_for_name)
async def card_name_received(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await message.answer("🎲 Выберите редкость карты:", reply_markup=create_rarity_keyboard())
    await state.set_state(AddCardState.waiting_for_rarity)

# 🔹 Обработка редкости через inline-кнопку
@dobcards_router.callback_query(F.data.startswith("rarity_"))
async def card_rarity_received(callback: types.CallbackQuery, state: FSMContext):
    rarity = callback.data.split("_", 1)[1]

    if rarity not in RARITY_RANGES:
        await callback.answer("❌ Неверная редкость!", show_alert=True)
        return

    card_data = await state.get_data()
    name, photo_path, universe = card_data["name"], card_data["photo_path"], card_data["universe"]
    
    db = await db_instance.get_connection()
    async with db.execute(f"SELECT 1 FROM {universe} WHERE name = ?", (name,)) as cursor:
        if await cursor.fetchone():
            await callback.message.answer(f"❌ Карта *{escape_markdown(name)}* уже существует!", parse_mode="MarkdownV2")
            await state.clear()
            return

    attack = random.randint(*RARITY_RANGES[rarity]["attack"])
    hp = random.randint(*RARITY_RANGES[rarity]["hp"])
    points = random.choice(range(RARITY_POINTS[rarity][0], RARITY_POINTS[rarity][1] + 1, 50))

    await db.execute(f"""
        INSERT INTO {universe} (name, photo_path, rarity, attack, hp, points)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, photo_path, rarity, attack, hp, points))
    await db.commit()

    try:
        await callback.message.answer(
            escape_markdown(
                f"✅ Карта {name} успешно добавлена в {universe.capitalize()}!\n\n"
                f"📋 Характеристики:\n"
                f"🎲 Редкость: {rarity.capitalize()}\n"
                f"⚔️ Атака: {attack}\n"
                f"❤️ Здоровье: {hp}\n"
                f"🎖 Очки: {points}"
            ),
            parse_mode="MarkdownV2"
        )
    except TelegramNetworkError:
        await callback.message.answer("🚨 Ошибка сети! Попробуйте снова.")

    await state.clear()
