import logging
import asyncio
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance  # Асинхронная БД

logging.basicConfig(level=logging.INFO)


async def get_user_id_by_username(bot: Bot, chat_id: int, username: str) -> int | None:
    """
    Получает user_id по username:
    1. Проверяет в базе (chat_users).
    2. Ищет среди администраторов.
    3. Проверяет через get_chat_member.
    """
    if not username:
        logging.warning("⚠️ Пустой username передан")
        return None

    username = username.strip().lstrip("@").lower()
    logging.info(f"🔍 Поиск user_id по username: {username} в чате {chat_id}")

    # 1. Проверяем в БД
    db = await db_instance.get_connection()
    try:
        async with db.execute(
            "SELECT user_id FROM chat_users WHERE chat_id = ? AND LOWER(username) = ?",
            (chat_id, username),
        ) as cursor:
            result = await cursor.fetchone()
        if result:
            logging.info(f"✅ Найден user_id в БД: {result[0]}")
            return result[0]
    except Exception as e:
        logging.error(f"❌ Ошибка при поиске в БД: {e}")
    finally:
        await db.close()

    # 2. Ищем среди администраторов
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        for admin in chat_admins:
            if admin.user.username and admin.user.username.lower() == username:
                logging.info(f"✅ Найден user_id среди админов: {admin.user.id}")
                return admin.user.id
        await asyncio.sleep(0.1)  # Задержка после запроса
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при поиске среди админов: {e}")

    # 3. Проверяем через get_chat_member
    try:
        chat_member = await bot.get_chat_member(chat_id, username)
        logging.info(f"✅ Найден user_id через get_chat_member: {chat_member.user.id}")
        return chat_member.user.id
    except TelegramAPIError:
        logging.warning(f"⚠️ {username} не найден через get_chat_member")
        await asyncio.sleep(0.1)  # Задержка после запроса

    logging.warning(f"⚠️ Не удалось найти user_id для {username}")
    return None


async def get_chat_members(bot: Bot, chat_id: int):
    """Получает всех участников чата из БД и проверяет актуальность."""
    logging.info(f"🔍 Получение списка участников для чата {chat_id}...")

    users = set()  # Используем set для уникальности

    try:
        # 1. Получаем участников из БД
        db = await db_instance.get_connection()
        try:
            async with db.execute(
                "SELECT user_id, username FROM chat_users WHERE chat_id = ? AND left = 0",
                (chat_id,),
            ) as cursor:
                db_users = await cursor.fetchall()
            for row in db_users:
                user_id, username = row[0], row[1]
                username = f"@{username}" if username else "(без username)"
                users.add((user_id, username))
        except Exception as e:
            logging.error(f"❌ Ошибка при запросе к БД: {e}")
        finally:
            await db.close()

        # 2. Добавляем администраторов
        try:
            chat_admins = await bot.get_chat_administrators(chat_id)
            for admin in chat_admins:
                user_id = admin.user.id
                username = f"@{admin.user.username}" if admin.user.username else "(без username)"
                users.add((user_id, username))
                if admin.user.is_bot:
                    logging.info(f"🤖 Обнаружен бот-админ: {user_id} (@{admin.user.username})")
            await asyncio.sleep(0.1)  # Задержка после запроса
        except TelegramAPIError as e:
            logging.error(f"❌ Ошибка при получении админов: {e}")

        logging.info(f"👥 Найдено участников: {len(users)}")

    except Exception as e:
        logging.error(f"❌ Ошибка при получении списка участников: {e}")
        return f"❌ Ошибка: {e}"

    return list(users)