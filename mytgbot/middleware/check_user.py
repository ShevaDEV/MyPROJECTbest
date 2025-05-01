import aiosqlite
import asyncio
import logging
import time
from aiogram import types, Bot
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from cards.universe_choice import select_universe
from handlers.usershand.referal import check_referral_validity
from dabase.database import db_instance
from handlers.satefy.user_utils import is_admin_or_owner
from utils.telegram_safe_request import safe_telegram_request
class CheckUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Update, data: dict):
        """Проверяет, зарегистрирован ли пользователь, обрабатывает рефералов, логирует сообщения и проверяет админские права."""
        bot: Bot = data["bot"]
        message = event.message if isinstance(event, types.Message) else None

        if not message or not message.from_user:
            return await handler(event, data)

        user_id = message.from_user.id
        chat_id = message.chat.id
        chat_type = message.chat.type

        # Проверка админских прав
        admin_commands = ["/setwelcome", "/clearwelcome", "/mute", "/unmute", "/dmute"]
        if message.text and any(message.text.startswith(cmd) for cmd in admin_commands):
            if chat_type in ["group", "supergroup"]:
                if not await is_admin_or_owner(bot, user_id, chat_id):
                    await safe_telegram_request(
                        lambda session: message.answer("🚫 Эта команда доступна только администраторам или владельцу.")
                    )
                    return False

        try:
            async with db_instance.get_db() as db:
                db.row_factory = aiosqlite.Row

                # Логирование сообщений для групповых чатов с purge_period
                if chat_type in ["group", "supergroup"]:
                    async with db.execute(
                        "SELECT purge_period FROM chat_settings WHERE chat_id = ?",
                        (chat_id,)
                    ) as cursor:
                        result = await cursor.fetchone()
                    if result and result["purge_period"] > 0:
                        await db.execute("""
                            INSERT OR IGNORE INTO messages (message_id, chat_id, user_id, timestamp)
                            VALUES (?, ?, ?, ?)
                        """, (message.message_id, chat_id, user_id, int(time.time())))
                        await db.commit()
                        logging.info(f"📩 Сообщение {message.message_id} от пользователя {user_id} записано для чата {chat_id}")

                # Проверка пользователя
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
                    # Для групп пропускаем даже без selected_universe
                    if chat_type in ["group", "supergroup"]:
                        return await handler(event, data)
                    # Для лички требуем selected_universe
                    if not user_data["selected_universe"]:
                        await select_universe(message, bot)
                        return False
                    return await handler(event, data)

                # Новый пользователь
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
                logging.info(f"Новый пользователь {user_id} зарегистрирован")

                if referrer_id:
                    await check_referral_validity(user_id, bot)

                # В группах пропускаем после регистрации
                if chat_type in ["group", "supergroup"]:
                    return await handler(event, data)
                # В личке требуем выбор вселенной
                await select_universe(message, bot)
                return False

        except RuntimeError as e:
            await safe_telegram_request(
                lambda session: message.answer(str(e))
            )
            return False