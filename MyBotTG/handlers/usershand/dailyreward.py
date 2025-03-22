import aiosqlite
import logging
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command

dailyreward_router = Router()

# Получение текущего времени в формате для базы данных
def get_current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Вычисление бонуса
def calculate_bonus(streak: int) -> int:
    """Вычисляет бонус на основе текущего стрика."""
    return min(streak, 7)  # Максимум 7 прокруток

# Ежедневный бонус
async def give_daily_bonus(user_id: int) -> tuple[bool, int, int, str]:
    """
    Выдает ежедневный бонус, если прошло 24 часа.
    Если пользователь пропустил хотя бы 1 день — стрик сбрасывается.
    
    :param user_id: ID пользователя
    :return: (успех, новый стрик, полученный бонус, время до следующего бонуса)
    """
    try:
        async with aiosqlite.connect("bot_database.db") as conn:
            cursor = await conn.execute("""
                SELECT last_claimed, daily_streak 
                FROM users 
                WHERE user_id = ?
            """, (user_id,))
            user_data = await cursor.fetchone()

            now = datetime.now()

            if not user_data or not user_data[0]:
                # Если данных нет, создаем начальную запись
                await conn.execute("""
                    UPDATE users
                    SET last_claimed = ?, daily_streak = 1, spins = spins + 1
                    WHERE user_id = ?
                """, (get_current_time(), user_id))
                await conn.commit()
                return True, 1, 1, ""  # Выдан 1 бонус, время до следующего бонуса - пусто

            last_claimed, daily_streak = user_data
            last_claimed_time = datetime.strptime(last_claimed, '%Y-%m-%d %H:%M:%S')

            hours_since_last_claim = (now - last_claimed_time).total_seconds() / 3600

            if hours_since_last_claim < 24:
                remaining_time = timedelta(hours=24) - (now - last_claimed_time)
                return False, daily_streak, 0, str(remaining_time).split('.')[0]  # Возвращаем время до бонуса

            # Проверяем, прошло ли более 48 часов, сбрасываем стрик, если да
            if hours_since_last_claim >= 48:
                daily_streak = 0  # Сбрасываем стрик

            # Вычисляем бонус (1-7 прокруток в зависимости от стрика)
            bonus = calculate_bonus(daily_streak + 1)

            await conn.execute("""
                UPDATE users
                SET last_claimed = ?, daily_streak = ?, spins = spins + ?
                WHERE user_id = ?
            """, (get_current_time(), daily_streak + 1, bonus, user_id))
            await conn.commit()

            return True, daily_streak + 1, bonus, ""  # ✅ Теперь возвращает только бонус и пустую строку для времени
    except Exception as e:
        logging.error(f"Ошибка при выдаче ежедневного бонуса: {e}")
        return False, 0, 0, ""

# Хендлер команды /daily
@dailyreward_router.message(Command("daily"))
@dailyreward_router.message(F.text.lower() == "дейли")
async def daily_reward(message: types.Message):
    user_id = message.from_user.id
    success, streak, bonus, remaining_time = await give_daily_bonus(user_id)

    if success:
        reward_message = (
            f"🎁 *Вы получили свой ежедневный бонус!*\n\n"
            f"🌟 Стрик: *{streak}* день(ей).\n"
            f"🔄 Вы получили: *{bonus}* прокруток."
        )
    else:
        reward_message = (
            f"⏳ *Вы уже получили бонус сегодня.*\n\n"
            f"🌟 Стрик: *{streak}* день(ей).\n"
            f"Попробуйте снова через: *{remaining_time}*."
        )

    await message.answer(reward_message, parse_mode="Markdown")
