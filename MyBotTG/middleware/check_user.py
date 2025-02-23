import sqlite3
from aiogram import types, Router, Bot
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from cards.universe_choice import select_universe
from handlers.usershand.referal import check_referral_validity  # ✅ Импортируем
from config import CHANNEL_ID

class CheckUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Update, data: dict):
        """Проверяет, зарегистрирован ли пользователь, и обрабатывает рефералов."""
        bot: Bot = data["bot"]  # Получаем объект бота
        message = event.message if isinstance(event.message, types.Message) else None

        # Если нет сообщения или пользователя — продолжаем обработку
        if not message or not message.from_user:
            return await handler(event, data)

        user_id = message.from_user.id

        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()

        # Проверяем, зарегистрирован ли пользователь
        cursor.execute("SELECT user_id, is_blacklisted, selected_universe FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()

        if user_data:
            if user_data[1]:  # Если в бане
                await message.answer("🚫 У вас нет доступа к боту.")
                return False  

            # Если вселенная не выбрана, предлагаем выбрать
            if not user_data[2]:
                await select_universe(message)
                return False  

            return await handler(event, data)  # Пользователь зарегистрирован → продолжаем обработку

        # Новый пользователь → регистрация
        referrer_id = None
        if message.text and message.text.startswith("/start "):
            parts = message.text.split()
            if len(parts) > 1 and parts[1].isdigit():  
                referrer_id = int(parts[1])

        cursor.execute("""
            INSERT INTO users (user_id, username, registration_date)
            VALUES (?, ?, datetime('now'))
        """, (user_id, message.from_user.username))
        conn.commit()

        # Если есть реферальный код → обрабатываем реферала
        if referrer_id:
            await check_referral_validity(user_id, bot)  # ✅ Исправлено

        conn.close()

        # После регистрации сразу предлагаем выбрать вселенную
        await select_universe(message)
        return False  # Прерываем обработку, пока не выберет вселенную
