from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from datetime import datetime, timedelta
import sqlite3
import logging

dailyreward_router = Router()

# Получение текущего времени в формате для базы данных
def get_current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Вычисление бонуса
def calculate_bonus(streak: int) -> int:
    """Вычисляет бонус на основе текущего стрика."""
    return min(streak + 1, 7)

# Ежедневный бонус
async def give_daily_bonus(user_id: int) -> tuple[bool, int, int]:
    """
    Выдает ежедневный бонус, если прошло 24 часа.
    :param user_id: ID пользователя
    :return: (успех, новый стрик, общее количество прокруток)
    """
    try:
        with sqlite3.connect("bot_database.db") as conn:
            cursor = conn.cursor()

            # Получаем данные пользователя
            cursor.execute("""
                SELECT last_claimed, daily_streak, spins 
                FROM users 
                WHERE user_id = ?
            """, (user_id,))
            user_data = cursor.fetchone()

            if not user_data or not user_data[0]:
                # Если данных нет, создаем начальную запись
                cursor.execute("""
                    UPDATE users
                    SET last_claimed = ?, daily_streak = 1, spins = spins + 1
                    WHERE user_id = ?
                """, (get_current_time(), user_id))
                conn.commit()
                return True, 1, 1

            last_claimed, daily_streak, spins = user_data
            last_claimed_time = datetime.strptime(last_claimed, '%Y-%m-%d %H:%M:%S')

            # Проверяем, прошло ли 24 часа
            if datetime.now() - last_claimed_time < timedelta(hours=24):
                return False, daily_streak, spins

            # Вычисляем бонус и обновляем данные
            bonus = calculate_bonus(daily_streak)
            cursor.execute("""
                UPDATE users
                SET last_claimed = ?, daily_streak = daily_streak + 1, spins = spins + ?
                WHERE user_id = ?
            """, (get_current_time(), bonus, user_id))
            conn.commit()

            return True, daily_streak + 1, spins + bonus
    except Exception as e:
        logging.error(f"Ошибка при выдаче ежедневного бонуса: {e}")
        return False, 0, 0

# Генерация клавиатуры
def create_daily_reward_keyboard(enable_button: bool) -> InlineKeyboardMarkup:
    """Создает клавиатуру для ежедневного бонуса."""
    if enable_button:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Получить бонус", callback_data="get_daily_bonus")]
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=[])

# Обработка бонуса
async def process_daily_bonus(user_id: int) -> tuple[str, InlineKeyboardMarkup, bool]:
    """
    Обрабатывает выдачу ежедневного бонуса.
    :param user_id: ID пользователя
    :return: Сообщение, клавиатура, флаг успеха
    """
    success, streak, spins = await give_daily_bonus(user_id)

    if success:
        message = (
            f"🎁 *Вы получили свой ежедневный бонус!*\n\n"
            f"🌟 Стрик: *{streak}* день(ей)\n"
            f"🔄 Вы получили: *{spins}* прокруток."
        )
    else:
        message = (
            f"⏳ *Вы уже получили бонус сегодня.*\n\n"
            f"🌟 Стрик: *{streak}* день(ей).\n"
            f"Попробуйте снова через 24 часа."
        )

    return message, create_daily_reward_keyboard(enable_button=success), success

# Хендлер команды /daily
@dailyreward_router.message(Command("daily"))
async def daily_reward(message: types.Message):
    user_id = message.from_user.id
    reward_message, keyboard, _ = await process_daily_bonus(user_id)
    await message.answer(reward_message, reply_markup=keyboard, parse_mode="Markdown")

# Хендлер инлайн-кнопки
@dailyreward_router.callback_query(lambda cb: cb.data == "get_daily_bonus")
async def handle_get_daily_bonus(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    reward_message, keyboard, success = await process_daily_bonus(user_id)

    try:
        await callback_query.message.edit_text(reward_message, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка при обновлении сообщения: {e}")
    await callback_query.answer("Бонус обработан!" if success else "Бонус уже получен.")
