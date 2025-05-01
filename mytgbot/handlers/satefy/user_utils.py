import logging
import asyncio
import re
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance  # Асинхронная БД

logging.basicConfig(level=logging.INFO)

async def get_user_id_by_username(bot: Bot, chat_id: int, username: str) -> int | None:
    """
    Получает user_id по username:
    1️⃣ Проверяет в базе (chat_users).
    2️⃣ Ищет среди администраторов.
    """
    if not username:
        logging.warning("⚠️ Пустой username передан")
        return None

    username = username.strip().lstrip("@").lower()
    logging.info(f" Поиск user_id по username: {username} в чате {chat_id}")

    # 1️⃣ Проверяем в БД (chat_users)
    db = await db_instance.get_connection()
    try:
        async with db.execute(
            "SELECT user_id FROM chat_users WHERE chat_id = ? AND LOWER(username) = ? AND left = 0",
            (chat_id, username),
        ) as cursor:
            result = await cursor.fetchone()
        if result:
            logging.info(f"✅ Найден user_id в БД: {result[0]}")
            return result[0]
        else:
            logging.warning(f"⚠️ Пользователь @{username} не найден в chat_users для chat_id={chat_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка при поиске в БД: {e}")
    finally:
        await db.close()

    # 2️⃣ Ищем среди администраторов
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        for admin in chat_admins:
            if admin.user.username and admin.user.username.lower() == f"@{username}":
                logging.info(f"✅ Найден user_id среди админов: {admin.user.id}")
                return admin.user.id
        await asyncio.sleep(0.1)  # Задержка после запроса
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при поиске среди админов: {e}")

    logging.warning(f"⚠️ Не удалось найти user_id для @{username}")
    return None

async def get_chat_members(bot: Bot, chat_id: int):
    """Получает всех участников чата из БД и проверяет актуальность."""
    logging.info(f" Получение списка участников для чата {chat_id}...")

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
                    logging.info(f" Обнаружен бот-админ: {user_id} (@{admin.user.username})")
            await asyncio.sleep(0.1)  # Задержка после запроса
        except TelegramAPIError as e:
            logging.error(f"❌ Ошибка при получении админов: {e}")

        logging.info(f" Найдено участников: {len(users)}")

    except Exception as e:
        logging.error(f"❌ Ошибка при получении списка участников: {e}")
        return f"❌ Ошибка: {e}"

    return list(users)

async def is_admin_or_owner(bot: Bot, user_id: int, chat_id: int) -> bool:
    """Проверяет, является ли пользователь админом или владельцем в чате."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status == "creator":
            await update_user_role_in_db(user_id, chat_id, "owner")
            return True
        elif member.status == "administrator":
            await update_user_role_in_db(user_id, chat_id, "admin")
            return True
    except TelegramAPIError as e:
        logging.error(f"Ошибка при проверке через API: {e}")

    # Запасной вариант через базу
    conn = await db_instance.get_connection()
    try:
        async with conn.execute(
            "SELECT role FROM chat_users WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row and row["role"] in ["admin", "owner"]
    except Exception as e:
        logging.error(f"Ошибка при проверке роли в базе для user_id {user_id} в чате {chat_id}: {e}")
        return False
    finally:
        await conn.close()

async def get_mention(bot: Bot, chat_id: int, user_id: int) -> str:
    """Получает упоминание пользователя (username или full_name)."""
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        if chat_member.user.username:
            return f"@{chat_member.user.username}"
        return f"[{escape_markdown(chat_member.user.full_name)}](tg://user?id={user_id})"
    except TelegramAPIError:
        return f"[Пользователь](tg://user?id={user_id})"

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)  # Экранирование всех символов

async def update_user_role_in_db(user_id: int, chat_id: int, role: str):
    """Обновляет роль пользователя в базе данных."""
    conn = await db_instance.get_connection()
    try:
        await conn.execute(
            "INSERT OR REPLACE INTO chat_users (user_id, chat_id, role, left) VALUES (?, ?, ?, 0)",
            (user_id, chat_id, role)
        )
        await conn.commit()
        logging.info(f"Роль пользователя {user_id} обновлена в базе как {role} для чата {chat_id}")
    except Exception as e:
        logging.error(f"Ошибка при обновлении роли в базе для user_id {user_id} в чате {chat_id}: {e}")
    finally:
        await conn.close()