import aiosqlite
import asyncio
from aiogram import types, Bot
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from cards.universe_choice import select_universe
from handlers.usershand.referal import check_referral_validity
from dabase.database import db_instance
from utils.telegram_safe_request import safe_telegram_request  # Импортируем новый модуль

class CheckUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Update, data: dict):
        """Проверяет, зарегистрирован ли пользователь, и обрабатывает рефералов."""
        bot: Bot = data["bot"]
        message = event.message if isinstance(event, types.Message) else None

        if not message or not message.from_user:
            return await handler(event, data)

        user_id = message.from_user.id

        try:
            async with db_instance.get_db() as db:  # ✅ Открываем соединение с БД
                db.row_factory = aiosqlite.Row

                async with db.execute(
                    "SELECT user_id, is_blacklisted, selected_universe FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    user_data = await cursor.fetchone()

                if user_data:
                    if user_data["is_blacklisted"]:
                        await safe_telegram_request(
                            lambda session: message.answer("🚫 У вас нет доступа к боту.")
                        )
                        return False

                    if not user_data["selected_universe"]:
                        await select_universe(message, bot)  # Передаем bot для использования safe_telegram_request
                        return False

                    return await handler(event, data)

                # 🚀 Новый пользователь → регистрация
                referrer_id = None
                if message.text and message.text.startswith("/start "):
                    parts = message.text.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        referrer_id = int(parts[1])

                await db.execute("""
                    INSERT INTO users (user_id, username, registration_date)
                    VALUES (?, ?, datetime('now'))
                """, (user_id, message.from_user.username))
                await db.commit()

                # 🔗 Проверяем реферальную систему
                if referrer_id:
                    await check_referral_validity(user_id, bot)  # Передаем bot для использования safe_telegram_request

                await select_universe(message, bot)  # Передаем bot для использования safe_telegram_request
                return False
        except RuntimeError as e:
            await safe_telegram_request(
                lambda session: message.answer(str(e))
            )
            return False