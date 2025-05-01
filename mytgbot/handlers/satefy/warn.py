import time
import logging
import re
import asyncio
from datetime import datetime
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatPermissions
from dabase.database import db_instance
from handlers.satefy.user_utils import get_user_id_by_username

logging.basicConfig(level=logging.INFO)
warn_router = Router()

# 🔴 Настройки варнов
WARN_LIMIT = 3  # Лимит варнов перед мутом
MUTE_DURATION = 7 * 24 * 60 * 60  # Мут на 7 дней
WARN_EXPIRE = 7 * 24 * 60 * 60  # Варн истекает через 7 дней

# Константы для сообщений
ADMIN_ONLY_ERROR = "🚫 *Ошибка:* Эта команда доступна только администраторам и владельцу чата\\."
USER_NOT_FOUND_ERROR = "⚠️ *Ошибка:* Не удалось найти пользователя\\."
INVALID_INPUT_ERROR = "⚠️ *Ошибка:* Укажите ID или username пользователя, либо ответьте на его сообщение\\."
DWARN_REPLY_ERROR = "⚠️ *Ошибка:* Используйте /dwarn в ответ на сообщение, которое нужно удалить\\."
SELF_WARN_ERROR = "❌ *Вы не можете выдать варн самому себе\\!*"
BOT_WARN_ERROR = "🤖 *Ботам нельзя выдавать варны\\!*"
OWNER_WARN_ERROR = "👑 *Ошибка:* Нельзя выдавать варны владельцу чата\\!"
ADMIN_WARN_ERROR = "🛡 *Ошибка:* Нельзя выдавать варны администраторам\\!"
NO_WARNS_MESSAGE = "✅ *У {mention} нет активных варнов\\.*"
API_ERROR = "❌ *Ошибка:* Не удалось получить данные пользователя\\."

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

async def get_user_id_from_message(message: types.Message, bot: Bot) -> tuple[int | None, str | None]:
    """Определяет user_id и корректное MarkdownV2-упоминание пользователя."""
    text_lines = message.text.strip().split("\n", 1)
    args = text_lines[0].split(maxsplit=1)

    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        user_name = escape_markdown(user.full_name or user.username or "Пользователь")
        mention = f"[{user_name}](tg://user?id={user.id})"
        return user.id, mention

    if len(args) > 1:
        username_or_id = args[1]
        if username_or_id.isdigit():
            return int(username_or_id), f"[Пользователь](tg://user?id={username_or_id})"
        elif username_or_id.startswith("@"):
            user_id = await get_user_id_by_username(bot, message.chat.id, username_or_id)
            if user_id:
                try:
                    user = await bot.get_chat_member(message.chat.id, user_id)
                    user_name = escape_markdown(user.user.full_name or username_or_id)
                    return user_id, f"[{user_name}](tg://user?id={user_id})"
                except TelegramAPIError:
                    return user_id, f"[Пользователь](tg://user?id={user_id})"

    return None, None

async def delete_message_safe(bot: Bot, chat_id: int, message_id: int) -> bool:
    """🔍 Безопасно удаляет сообщение, если у бота есть права."""
    try:
        chat = await bot.get_chat(chat_id)
        chat_member = await chat.get_member(bot.id)
        if chat_member.can_delete_messages:
            await bot.delete_message(chat_id, message_id)
            logging.info(f"✅ Сообщение {message_id} удалено из чата {chat_id}")
            return True
        else:
            logging.info(f"ℹ️ Бот не имеет прав удалять сообщения в чате {chat_id}")
            return False
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при удалении сообщения {message_id} в чате {chat_id}: {e}")
        return False

@warn_router.message(Command("warn"))
async def cmd_warn(message: types.Message, bot: Bot):
    """📌 Команда для выдачи варна в формате: /warn username\nпричина (опционально)."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    text_lines = message.text.strip().split("\n", 1)
    if len(text_lines[0].split()) < 2 and not message.reply_to_message:
        await message.reply(INVALID_INPUT_ERROR, parse_mode="MarkdownV2")
        return

    user_id, mention = await get_user_id_from_message(message, bot)
    if not user_id:
        await message.reply(USER_NOT_FOUND_ERROR, parse_mode="MarkdownV2")
        return

    if user_id == moderator_id:
        await message.reply(SELF_WARN_ERROR, parse_mode="MarkdownV2")
        return

    if user_id == bot.id:
        await message.reply(BOT_WARN_ERROR, parse_mode="MarkdownV2")
        return

    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        await asyncio.sleep(0.1)
    except TelegramAPIError:
        await message.reply(API_ERROR, parse_mode="MarkdownV2")
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await message.reply(OWNER_WARN_ERROR, parse_mode="MarkdownV2")
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await message.reply(ADMIN_WARN_ERROR, parse_mode="MarkdownV2")
        return

    reason = escape_markdown(text_lines[1]) if len(text_lines) > 1 else ""

    warns = await warn_user(chat_id, user_id, moderator_id, reason)

    if warns >= WARN_LIMIT:
        await mute_user(bot, chat_id, user_id, mention)
        await message.answer(f"🚫 *{mention} получил {warns} варна и теперь в муте на 7 дней\\!*", parse_mode="MarkdownV2")
    else:
        response = f"⚠️ *{mention} получил варн\\!*\n📊 *Всего варнов:* {warns}/{WARN_LIMIT}"
        if reason:
            response += f"\n📌 *Причина:* {reason}"
        await message.answer(response, parse_mode="MarkdownV2")

@warn_router.message(Command("dwarn"))
async def cmd_dwarn(message: types.Message, bot: Bot):
    """📌 Команда для выдачи варна с удалением сообщения, на которое ответили."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    if not message.reply_to_message:
        await message.reply(DWARN_REPLY_ERROR, parse_mode="MarkdownV2")
        return

    user_id, mention = await get_user_id_from_message(message, bot)
    if not user_id:
        await message.reply(USER_NOT_FOUND_ERROR, parse_mode="MarkdownV2")
        return

    if user_id == moderator_id:
        await message.reply(SELF_WARN_ERROR, parse_mode="MarkdownV2")
        return

    if user_id == bot.id:
        await message.reply(BOT_WARN_ERROR, parse_mode="MarkdownV2")
        return

    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        await asyncio.sleep(0.1)
    except TelegramAPIError:
        await message.reply(API_ERROR, parse_mode="MarkdownV2")
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await message.reply(OWNER_WARN_ERROR, parse_mode="MarkdownV2")
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await message.reply(ADMIN_WARN_ERROR, parse_mode="MarkdownV2")
        return

    text_lines = message.text.strip().split("\n", 1)
    reason = escape_markdown(text_lines[1]) if len(text_lines) > 1 else ""

    deleted = await delete_message_safe(bot, chat_id, message.reply_to_message.message_id)

    warns = await warn_user(chat_id, user_id, moderator_id, reason)

    delete_text = " и сообщение удалено" if deleted else " (сообщение не удалено — нет прав)"
    if warns >= WARN_LIMIT:
        await mute_user(bot, chat_id, user_id, mention)
        await message.answer(f"🚫 *{mention} получил {warns} варна и теперь в муте на 7 дней\\!*{delete_text}", 
                             parse_mode="MarkdownV2")
    else:
        response = f"⚠️ *{mention} получил варн\\!*{delete_text}\n📊 *Всего варнов:* {warns}/{WARN_LIMIT}"
        if reason:
            response += f"\n📌 *Причина:* {reason}"
        await message.answer(response, parse_mode="MarkdownV2")

@warn_router.message(Command("unwarn"))
async def cmd_unwarn(message: types.Message, bot: Bot):
    """📌 Команда для снятия последнего варна."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    user_id, mention = await get_user_id_from_message(message, bot)
    if not user_id:
        await message.reply(INVALID_INPUT_ERROR, parse_mode="MarkdownV2")
        return

    warns = await get_active_warns(chat_id, user_id)
    if warns == 0:
        await message.reply(NO_WARNS_MESSAGE.format(mention=mention), parse_mode="MarkdownV2")
        return

    await remove_warn(chat_id, user_id)
    warns -= 1

    await message.reply(
        f"✅ *Снят последний варн у {mention}\\.*\n📊 *Осталось варнов:* {warns}/{WARN_LIMIT}", 
        parse_mode="MarkdownV2"
    )

@warn_router.message(Command("warns"))
async def cmd_warns(message: types.Message, bot: Bot):
    """📌 Команда для просмотра активных варнов пользователя."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    user_id, mention = await get_user_id_from_message(message, bot)
    if not user_id:
        await message.reply(INVALID_INPUT_ERROR, parse_mode="MarkdownV2")
        return

    warns = await get_active_warns_details(chat_id, user_id)
    if not warns:
        await message.reply(NO_WARNS_MESSAGE.format(mention=mention), parse_mode="MarkdownV2")
        return

    response = f"📊 *У {mention} {len(warns)}/{WARN_LIMIT} активных варнов:*\n"
    for i, warn in enumerate(warns, 1):
        mod_id = warn['moderator_id']
        try:
            mod = await bot.get_chat_member(chat_id, mod_id)
            mod_mention = f"@{mod.user.username}" if mod.user.username else f"[ID: {mod_id}]"
        except TelegramAPIError:
            mod_mention = f"[ID: {mod_id}]"
        
        reason = warn['reason'] if warn['reason'] else "Причина не указана"
        timestamp = datetime.fromtimestamp(warn['timestamp']).strftime("%d.%m.%Y %H:%M")
        response += f"{i}\\. *Причина:* {escape_markdown(reason)}\n" \
                    f"   *Выдал:* {mod_mention}\n" \
                    f"   *Когда:* {timestamp}\n"

    await message.reply(response, parse_mode="MarkdownV2")

async def warn_user(chat_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """✅ Выдаёт варн пользователю и записывает его в БД."""
    expire_at = int(time.time()) + WARN_EXPIRE
    db = await db_instance.get_connection()
    try:
        await db.execute("""
            INSERT INTO warns_log (chat_id, user_id, reason, moderator_id, timestamp, expire_at) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (chat_id, user_id, reason, moderator_id, int(time.time()), expire_at))
        await db.commit()
    except Exception as e:
        logging.error(f"❌ Ошибка при добавлении варна для пользователя {user_id}: {e}")
    finally:
        await db.close()

    return await get_active_warns(chat_id, user_id)

async def remove_warn(chat_id: int, user_id: int):
    """🗑 Удаляет последний варн (самый новый)."""
    db = await db_instance.get_connection()
    try:
        await db.execute("""
            DELETE FROM warns_log 
            WHERE rowid = (
                SELECT rowid FROM warns_log 
                WHERE chat_id = ? AND user_id = ? 
                ORDER BY timestamp DESC LIMIT 1
            )
        """, (chat_id, user_id))
        await db.commit()
    except Exception as e:
        logging.error(f"❌ Ошибка при удалении варна для пользователя {user_id}: {e}")
    finally:
        await db.close()

async def get_active_warns(chat_id: int, user_id: int) -> int:
    """📊 Подсчитывает только активные (не истекшие) варны."""
    await clean_expired_warns()
    db = await db_instance.get_connection()
    try:
        async with db.execute("""
            SELECT COUNT(*) FROM warns_log 
            WHERE chat_id = ? AND user_id = ? AND expire_at > ?
        """, (chat_id, user_id, int(time.time()))) as cursor:
            count = await cursor.fetchone()
        return count[0] if count else 0
    except Exception as e:
        logging.error(f"❌ Ошибка при подсчёте варнов для пользователя {user_id}: {e}")
        return 0
    finally:
        await db.close()

async def get_active_warns_details(chat_id: int, user_id: int) -> list:
    """Получает детали активных варнов пользователя."""
    await clean_expired_warns()
    db = await db_instance.get_connection()
    try:
        async with db.execute("""
            SELECT reason, moderator_id, timestamp 
            FROM warns_log 
            WHERE chat_id = ? AND user_id = ? AND expire_at > ?
            ORDER BY timestamp ASC
        """, (chat_id, user_id, int(time.time()))) as cursor:
            return await cursor.fetchall()
    except Exception as e:
        logging.error(f"❌ Ошибка при получении деталей варнов для пользователя {user_id}: {e}")
        return []
    finally:
        await db.close()

async def clean_expired_warns():
    """🗑 Удаляет устаревшие варны (старше 7 дней)."""
    db = await db_instance.get_connection()
    try:
        await db.execute("DELETE FROM warns_log WHERE expire_at <= ?", (int(time.time()),))
        await db.commit()
    except Exception as e:
        logging.error(f"❌ Ошибка при очистке устаревших варнов: {e}")
    finally:
        await db.close()

async def mute_user(bot: Bot, chat_id: int, user_id: int, mention: str):
    """🚫 Выдаёт мут пользователю на 7 дней."""
    until_time = int(time.time()) + MUTE_DURATION
    db = await db_instance.get_connection()
    try:
        await db.execute("""
            INSERT INTO moderation (chat_id, user_id, mute_until, timestamp)
            VALUES (?, ?, ?, ?) 
            ON CONFLICT(chat_id, user_id) DO UPDATE SET mute_until = ?, timestamp = ?
        """, (chat_id, user_id, until_time, int(time.time()), until_time, int(time.time())))
        await db.commit()
    except Exception as e:
        logging.error(f"❌ Ошибка при добавлении мута для пользователя {user_id}: {e}")
    finally:
        await db.close()

    try:
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(), until_date=until_time)
        await bot.send_message(chat_id, f"🔇 *{mention} получил мут на 7 дней\\!*", parse_mode="MarkdownV2")
        await asyncio.sleep(0.1)
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при муте пользователя {user_id}: {e}")