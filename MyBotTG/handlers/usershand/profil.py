from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dabase.database import db_instance  # Используем асинхронную БД
from handlers.usershand.change_universe import start_universe_change
from promo.promocode import promocode_keyboard  # Инлайн-клавиатура для промокодов

profile_router = Router()

def profile_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для профиля."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="use_promocode")],
        [InlineKeyboardButton(text="🃏 Мои карты", callback_data="view_cards")],
        [InlineKeyboardButton(text="🌌 Сменить вселенную", callback_data="change_universe")],
        [InlineKeyboardButton(text="🎟️ Рефералы", callback_data="view_referrals")]
    ])

@profile_router.message(Command("profile"))
@profile_router.message(F.text.lower() == "профиль")
async def show_profile(event: types.Message | types.CallbackQuery):
    """Команда для отображения профиля пользователя."""
    
    # Определяем user_id в зависимости от типа объекта
    user_id = event.from_user.id
    message = event.message if isinstance(event, types.CallbackQuery) else event

    db = await db_instance.get_connection()  # 🛠 Получаем активное соединение
    async with db.execute("SELECT total_points, spins, selected_universe FROM users WHERE user_id = ?", (user_id,)) as cursor:
        user_data = await cursor.fetchone()

    if not user_data:
        await message.answer("Ваш профиль не найден. Пожалуйста, зарегистрируйтесь с помощью команды /start.")
        return

    total_points, spins, selected_universe = user_data
    spins = spins or 0

    if not selected_universe:
        await message.answer(
            "Вы не выбрали вселенную! Используйте /select_universe, чтобы выбрать доступную вселенную."
        )
        return

    async with db.execute("SELECT COUNT(DISTINCT card_id) FROM user_cards WHERE user_id = ?", (user_id,)) as cursor:
        user_cards_count = (await cursor.fetchone())[0] or 0

    async with db.execute(f"SELECT COUNT(*) FROM [{selected_universe}]") as cursor:
        total_universe_cards = (await cursor.fetchone())[0] or 0

    profile_text = (
        f"👤 *Ваш профиль:*\n\n"
        f"🌌 *Выбранная вселенная:* {selected_universe.capitalize()}\n"
        f"💎 *Общее количество очков:* {total_points}\n"
        f"🔄 *Количество прокруток:* {spins}\n"
        f"🃏 *Карт:* {user_cards_count} из {total_universe_cards}\n\n"
        f"Вы можете использовать 🎁 *промокод* или 🃏 *посмотреть свои карты!*"
    )

    await message.answer(profile_text, parse_mode="Markdown", reply_markup=profile_keyboard())
