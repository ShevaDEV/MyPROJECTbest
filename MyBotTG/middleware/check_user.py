from aiogram import Router, types
from aiogram.types import Message
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
import sqlite3

class CheckUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Update, data: dict):
        # Получаем ID пользователя
        user_id = event.message.from_user.id if isinstance(event.message, types.Message) else None

        # Если это команда /start, пропускаем проверку
        if event.message and event.message.text == "/start":
            return await handler(event, data)

        if user_id:
            conn = sqlite3.connect("bot_database.db")
            cursor = conn.cursor()

            # Проверяем, зарегистрирован ли пользователь
            cursor.execute("SELECT EXISTS(SELECT 1 FROM users WHERE user_id = ?)", (user_id,))
            is_registered = cursor.fetchone()[0]

            # Проверяем, не находится ли пользователь в черном списке
            cursor.execute("SELECT is_blacklisted FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            is_blacklisted = result[0] if result else None

            conn.close()

            # Если пользователь не зарегистрирован или в черном списке, отменяем обработку
            if not is_registered:
                await event.message.answer("Пожалуйста, начните с команды /start, чтобы зарегистрироваться.")
                return False  # Блокируем обработку

            if is_blacklisted:
                await event.message.answer("Вы не можете использовать этого бота, так как он находится в вашем черном списке.")
                return False  # Блокируем обработку

        # Передаём управление следующему обработчику, если всё в порядке
        return await handler(event, data)

