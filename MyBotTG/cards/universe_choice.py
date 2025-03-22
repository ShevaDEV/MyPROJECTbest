from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import aiosqlite

AVAILABLE_UNIVERSES = ["marvel", "star_wars", "dc"]

universechoice_router = Router()


async def get_user_universe(user_id: int) -> str | None:
    """Получаем выбранную вселенную пользователя из базы данных."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT selected_universe FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
    return result[0] if result else None


async def set_user_universe(user_id: int, universe: str):
    """Сохраняем выбранную вселенную пользователя в базе данных."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE users SET selected_universe = ? WHERE user_id = ?", (universe, user_id))
        await db.commit()


# Команда для выбора вселенной
@universechoice_router.message(Command("select_universe"))
@universechoice_router.message(F.text.lower() == "выбрать вселенную")
async def select_universe(message: types.Message):
    user_id = message.from_user.id

    # Проверяем текущую вселенную
    current_universe = await get_user_universe(user_id)
    if current_universe:
        await message.answer(
            f"✅ Вы уже выбрали вселенную *{current_universe.capitalize()}*.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Генерируем кнопки выбора вселенной
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=universe.capitalize())] for universe in AVAILABLE_UNIVERSES],
        resize_keyboard=True,
    )

    await message.answer("🌌 *Выберите вселенную, чтобы получать карты:*", parse_mode="Markdown", reply_markup=keyboard)


# Обработчик выбора вселенной
@universechoice_router.message(F.text.lower().in_([u.lower() for u in AVAILABLE_UNIVERSES]))
async def universe_chosen(message: types.Message):
    user_id = message.from_user.id
    chosen_universe = message.text.lower()

    # Проверяем, если вселенная уже была выбрана
    current_universe = await get_user_universe(user_id)
    if current_universe == chosen_universe:
        await message.answer(
            f"✅ Вы уже выбрали вселенную *{chosen_universe.capitalize()}*.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Сохраняем выбор вселенной
    await set_user_universe(user_id, chosen_universe)

    await message.answer(
        f"🌟 Вы успешно выбрали вселенную *{chosen_universe.capitalize()}*.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
