from aiogram import Router, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite
from dabase.database import db_instance  # Используем асинхронную БД

leaderboard_router = Router()

def create_leaderboard_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру для обновления топа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_leaderboard")]
    ])

async def get_leaderboard_with_position(user_id: int) -> str:
    """
    Формирует текст топа-10 с позицией текущего пользователя.
    :param user_id: ID пользователя для отображения его позиции.
    :return: Отформатированный текст топа.
    """
    async with await db_instance.get_connection() as db:
        # Получаем топ-10 пользователей
        async with db.execute("""
            SELECT username, total_points
            FROM users
            WHERE total_points > 0
            ORDER BY total_points DESC
            LIMIT 10
        """) as cursor:
            top_users = await cursor.fetchall()

        # Определяем позицию текущего пользователя
        async with db.execute("""
            SELECT COUNT(*) + 1
            FROM users
            WHERE total_points > (SELECT total_points FROM users WHERE user_id = ?)
        """, (user_id,)) as cursor:
            user_position = (await cursor.fetchone())[0]

        # Получаем данные текущего пользователя
        async with db.execute("""
            SELECT username, total_points
            FROM users
            WHERE user_id = ?
        """, (user_id,)) as cursor:
            current_user_data = await cursor.fetchone()

    # Формируем текст топа
    leaderboard_text = "🏆 *Топ-10 пользователей по очкам сезона:*\n\n"
    for i, row in enumerate(top_users, start=1):
        username, points = row
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
        leaderboard_text += f"{medal} - {username or 'Безымянный'}: {points} очков\n"

    # Добавляем позицию текущего пользователя, если он не в топ-10
    if user_position > 10 and current_user_data:
        leaderboard_text += "\n"
        leaderboard_text += f"ℹ️ *Ваше место*: {user_position} ({current_user_data[0] or 'Безымянный'}: {current_user_data[1]} очков)"

    return leaderboard_text

@leaderboard_router.message(Command("top"))
@leaderboard_router.message(Command("leaders"))
@leaderboard_router.message(lambda message: message.text and message.text.lower() == "лидеры")
async def show_leaderboard(message: types.Message):
    """Отправляет топ-10 игроков с позицией текущего пользователя."""
    user_id = message.from_user.id

    # Формируем текст топа
    leaderboard_text = await get_leaderboard_with_position(user_id)

    # Отправляем сообщение с топом
    await message.answer(leaderboard_text, parse_mode="Markdown", reply_markup=create_leaderboard_keyboard())

@leaderboard_router.callback_query(lambda callback: callback.data == "refresh_leaderboard")
async def refresh_leaderboard(callback: types.CallbackQuery):
    """Обновляет сообщение с топом."""
    user_id = callback.from_user.id

    # Формируем текст топа
    leaderboard_text = await get_leaderboard_with_position(user_id)

    # Проверяем текущие текст и клавиатуру
    current_text = callback.message.text or ""
    current_reply_markup = callback.message.reply_markup

    new_reply_markup = create_leaderboard_keyboard()

    # Если текст и клавиатура совпадают, уведомляем пользователя
    if current_text == leaderboard_text and current_reply_markup == new_reply_markup:
        await callback.answer("Данные актуальны!")
        return

    # Обновляем текст сообщения
    try:
        await callback.message.edit_text(
            leaderboard_text,
            parse_mode="Markdown",
            reply_markup=new_reply_markup
        )
        await callback.answer("Топ обновлен!")
    except TelegramBadRequest as e:
        # Если ошибка возникает, например, из-за того, что текст не изменился
        if "message is not modified" in str(e):
            await callback.answer("Данные актуальны!")
        else:
            raise
