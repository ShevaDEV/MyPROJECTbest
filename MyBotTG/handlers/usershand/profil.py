from aiogram import Router, types, F
from aiogram.filters import Command
import sqlite3
from kbds.inlinecards import rarity_keyboard_for_user
from promo.promocode import promocode_keyboard  # Инлайн-клавиатура для промокодов

profile_router = Router()

def profile_keyboard() -> types.InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для профиля."""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="use_promocode")],
        [types.InlineKeyboardButton(text="📋 Мои карты", callback_data="view_cards")]
    ])

@profile_router.message(Command("profile"))
@profile_router.message(F.text.lower() == "профиль")
async def show_profile(message: types.Message):
    """Команда для отображения профиля пользователя."""
    user_id = message.from_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Запрос данных пользователя
    cursor.execute("SELECT total_points, spins, selected_universe FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.answer("Ваш профиль не найден. Пожалуйста, зарегистрируйтесь с помощью команды /start.")
        conn.close()
        return

    total_points, spins, selected_universe = user_data
    spins = spins if spins else 0

    if not selected_universe:
        await message.answer(
            "Вы не выбрали вселенную! Используйте /selectuniverse, чтобы выбрать доступную вселенную."
        )
        conn.close()
        return

    # Подсчитываем количество уникальных карт у пользователя
    cursor.execute("""
        SELECT COUNT(DISTINCT card_id)
        FROM user_cards
        WHERE user_id = ?
    """, (user_id,))
    user_cards_count = cursor.fetchone()[0] or 0

    # Подсчитываем общее количество карт во вселенной
    cursor.execute(f"SELECT COUNT(*) FROM [{selected_universe}]")
    total_universe_cards = cursor.fetchone()[0] or 0

    conn.close()

    # Формируем текст профиля
    profile_text = (
        f"👤 Ваш профиль:\n\n"
        f"🌌 Выбранная вселенная: {selected_universe.capitalize()}\n"
        f"🎖️ Общее количество очков: {total_points}\n"
        f"🔄 Количество прокруток: {spins}\n"
        f"📋 Карт: {user_cards_count} из {total_universe_cards}\n\n"
        f"Вы можете использовать 🎁 промокод или 📋 посмотреть свои карты!"
    )

    await message.answer(profile_text, reply_markup=profile_keyboard())
