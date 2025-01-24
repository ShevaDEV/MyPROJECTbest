from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from config import AVAILABLE_UNIVERSES

import sqlite3

universechoice_router = Router()

async def get_user_universe(user_id: int) -> str:
    """Получаем выбранную вселенную пользователя из базы данных."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None  # Возвращаем выбранную вселенную или None


async def set_user_universe(user_id: int, universe: str):
    """Сохраняем выбранную вселенную пользователя в базе данных."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET selected_universe = ? WHERE user_id = ?", (universe, user_id))
    conn.commit()
    conn.close()


# Команда для выбора вселенной
@universechoice_router.message(Command("select_universe"))
@universechoice_router.message(F.text.lower() == "выбрать вселенную")
async def select_universe(message: types.Message):
    user_id = message.from_user.id

    # Проверяем текущую вселенную
    current_universe = await get_user_universe(user_id)
    if current_universe:
        await message.answer(
            f"Вы уже выбрали вселенную {current_universe.capitalize()}.",
            reply_markup=ReplyKeyboardRemove()  # Убираем реплай-кнопки, если были
        )
        return

    # Генерируем кнопки
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=universe.capitalize())] for universe in AVAILABLE_UNIVERSES
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Выберите вселенную, чтобы получать карты:",
        reply_markup=keyboard
    )


# Обработчик выбора вселенной
@universechoice_router.message(F.text.lower().in_([u.lower() for u in AVAILABLE_UNIVERSES]))
async def universe_chosen(message: types.Message):
    user_id = message.from_user.id
    chosen_universe = message.text.lower()

    # Проверяем, если вселенная уже была выбрана
    current_universe = await get_user_universe(user_id)
    if current_universe == chosen_universe:
        await message.answer(
            f"Вы уже выбрали вселенную {chosen_universe.capitalize()}.",
            reply_markup=ReplyKeyboardRemove()  # Убираем реплай-кнопки
        )
        return

    # Сохраняем выбор вселенной
    await set_user_universe(user_id, chosen_universe)

    await message.answer(
        f"Вы успешно выбрали вселенную {chosen_universe.capitalize()}.",
        reply_markup=ReplyKeyboardRemove()  # Убираем реплай-кнопки
    )


# Команда для проверки текущей вселенной
@universechoice_router.message(Command("current_universe"))
@universechoice_router.message(F.text.lower() == "моя вселенная")
async def current_universe(message: types.Message):
    user_id = message.from_user.id

    # Получаем текущую вселенную пользователя
    current_universe = await get_user_universe(user_id)

    if current_universe:
        await message.answer(f"Ваша текущая вселенная: {current_universe.capitalize()}.")
    else:
        await message.answer("Вы еще не выбрали вселенную. Используйте команду /select_universe для выбора.")
