from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
import sqlite3
from datetime import datetime, timedelta

dailyreward_router = Router()

# Функция для получения текущего времени в формате, подходящем для базы данных
def get_current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Функция для начисления бонуса
async def give_daily_bonus(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Получаем время последнего сбора бонуса и текущий стрик
    cursor.execute("""
        SELECT last_claimed, daily_streak, spins FROM users WHERE user_id = ?
    """, (user_id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если данных о последнем сборе нет, создаем начальную запись
        cursor.execute("""
            UPDATE users
            SET last_claimed = ?, daily_streak = 1, spins = spins + 1
            WHERE user_id = ?
        """, (get_current_time(), user_id))
        conn.commit()
        conn.close()
        return True, 1, 1  # Первый день стрика, 1 прокрутка

    last_claimed, daily_streak, spins = user_data

    # Преобразуем строку в datetime
    last_claimed_time = datetime.strptime(last_claimed, '%Y-%m-%d %H:%M:%S')

    # Проверяем, прошло ли 24 часа
    if datetime.now() - last_claimed_time < timedelta(hours=24):
        conn.close()
        return False, daily_streak, spins  # Бонус нельзя собрать, если прошло меньше 24 часов

    # Рассчитываем бонус в зависимости от стрика (максимум 7 прокруток)
    bonus = min(daily_streak + 1, 7)

    # Если прошло более 24 часов, обновляем данные
    cursor.execute("""
        UPDATE users
        SET last_claimed = ?, daily_streak = daily_streak + 1, spins = spins + ?
        WHERE user_id = ?
    """, (get_current_time(), bonus, user_id))
    conn.commit()
    conn.close()

    return True, daily_streak + 1, spins + bonus  # Успех, обновленный стрик и бонус

# Функция для генерации кнопки и сообщения о ежедневном бонусе
def create_daily_reward_keyboard(enable_button: bool) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для ежедневного бонуса."""
    if enable_button:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Получить бонус", callback_data="get_daily_bonus")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[])

# Хендлер для команды /daily
@dailyreward_router.message(Command("daily"))
async def daily_reward(message: types.Message):
    user_id = message.from_user.id

    # Попытаться выдать ежедневный бонус
    success, streak, spins = await give_daily_bonus(user_id)

    if success:
        # Если бонус был получен
        reward_message = f"🎁 Вы получили свой ежедневный бонус!\n\n🌟 Стрик: {streak} день(ей)\n🔄 Вы получили: {spins} прокруток."
    else:
        # Если бонус еще нельзя получить
        reward_message = f"⏳ Вы уже получили бонус сегодня.\n\n🌟 Стрик: {streak} день(ей).\nПопробуйте снова через 24 часа."

    await message.answer(reward_message, reply_markup=create_daily_reward_keyboard(enable_button=success))

# Хендлер для инлайн кнопки "Получить бонус"
@dailyreward_router.callback_query(lambda cb: cb.data == "get_daily_bonus")
async def handle_get_daily_bonus(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    # Попытаться выдать бонус
    success, streak, spins = await give_daily_bonus(user_id)

    if success:
        # Если бонус был получен
        reward_message = f"🎁 Вы получили свой ежедневный бонус!\n\n🌟 Стрик: {streak} день(ей)\n🔄 Вы получили: {spins} прокруток."
    else:
        # Если бонус еще нельзя получить
        reward_message = f"⏳ Вы уже получили бонус сегодня.\n\n🌟 Стрик: {streak} день(ей).\nПопробуйте снова через 24 часа."

    # Обновляем сообщение только если есть изменения
    try:
        await callback_query.message.edit_text(
            reward_message,
            reply_markup=create_daily_reward_keyboard(enable_button=success)
        )
    except:
        pass
    await callback_query.answer()
