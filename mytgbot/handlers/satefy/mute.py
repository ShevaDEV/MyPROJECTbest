import time
import logging
import re
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatPermissions
from dabase.database import db_instance
from handlers.satefy.user_utils import get_user_id_by_username, is_admin_or_owner

logging.basicConfig(level=logging.INFO)
mute_router = Router()

# 🔴 Настройки мута
DEFAULT_MUTE_DURATION = 24 * 60 * 60  # 1 день по умолчанию

# Константы для сообщений (точки и спецсимволы экранированы вручную)
ADMIN_ONLY_ERROR = "🚫 *Ошибка:* Эта команда доступна только администраторам и владельцу чата\\."
INVALID_INPUT_ERROR = "⚠️ *Ошибка:* Укажите пользователя и время на первой строке, а причину на второй\\."
INVALID_USER_ERROR = "⚠️ *Ошибка:* Не удалось найти пользователя\\."
INVALID_DMUTE_INPUT_ERROR = "⚠️ *Ошибка:* Укажите время на первой строке, а причину на второй\\."
DMUTE_REPLY_ERROR = "⚠️ *Ошибка:* Используйте /dmute в ответ на сообщение, которое нужно удалить\\."
SELF_MUTE_ERROR = "❌ *Вы не можете замутить самого себя\\!*"
BOT_MUTE_ERROR = "🤖 *Ботам нельзя выдавать мут\\!*"
MUTE_ADMIN_ERROR = "⚠️ *Ошибка:* Нельзя замутить администратора чата\\."
MUTE_OWNER_ERROR = "⚠️ *Ошибка:* Нельзя замутить владельца чата\\."
MUTE_FAILED_ERROR = "⚠️ *Ошибка:* Не удалось выдать мут\\. Возможно, бот не является администратором\\."
MUTE_NOT_SUPERGROUP = "⚠️ *Ошибка:* Команда доступна только в супергруппах\\."
UNMUTE_FAILED_ERROR = "⚠️ *Ошибка:* Не удалось снять мут\\."
UNMUTE_INVALID_USER_ERROR = "⚠️ *Ошибка:* Укажите ID или username пользователя, или используйте команду в ответ на сообщение\\."

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2 в динамических строках."""
    if not text:
        return ""
    return re.sub(r"([_*[\]()~`>#+\-=|{}.!])", r"\\\1", text)

def parse_duration(duration: str) -> int:
    """🔍 Конвертирует строку (например, 3ч, 2д) в секунды."""
    match = re.match(r"(\d+)([чЧhHдДdD]?)", duration)
    if not match:
        return DEFAULT_MUTE_DURATION

    value, unit = match.groups()
    value = int(value)

    if unit.lower() in ["ч", "h"]:
        return value * 3600
    elif unit.lower() in ["д", "d"]:
        return value * 86400

    return DEFAULT_MUTE_DURATION

async def check_and_remove_mute(bot: Bot):
    """🔍 Проверяет истёк ли мут и снимает его."""
    now = int(time.time())
    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT chat_id, user_id FROM moderation WHERE mute_until > 0 AND mute_until <= ?", (now,)) as cursor:
            expired_mutes = await cursor.fetchall()

        for chat_id, user_id in expired_mutes:
            await unmute_user(bot, chat_id, user_id)
    finally:
        await db.close()

async def get_mention(bot: Bot, chat_id: int, user_id: int) -> str:
    """🔍 Получает упоминание пользователя (username или full_name)."""
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        if chat_member.user.username:
            return f"@{chat_member.user.username}"
        return f"[{escape_markdown(chat_member.user.full_name)}](tg://user?id={user_id})"
    except TelegramAPIError:
        return f"[Пользователь](tg://user?id={user_id})"

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

async def is_target_admin_or_owner(bot: Bot, chat_id: int, user_id: int) -> tuple[bool, bool]:
    """Проверяет, является ли целевой пользователь админом или владельцем."""
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        is_admin = chat_member.status == "administrator"
        is_owner = chat_member.status == "creator"
        return is_admin, is_owner
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при проверке статуса user_id {user_id} в чате {chat_id}: {e}")
        return False, False

@mute_router.message(Command("mute"))
async def cmd_mute(message: types.Message, bot: Bot):
    """📌 Команда для выдачи мута с вводом в 2 строки."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Проверяем, что чат — супергруппа
    if message.chat.type != "supergroup":
        await message.reply(MUTE_NOT_SUPERGROUP, parse_mode="MarkdownV2")
        return

    text_lines = message.text.strip().split("\n", 1)
    if len(text_lines) < 2:
        await message.reply(INVALID_INPUT_ERROR, parse_mode="MarkdownV2")
        return

    first_line = text_lines[0].split(maxsplit=2)
    if len(first_line) < 2:
        await message.reply("⚠️ *Ошибка:* Укажите username либо ID и время мута\\.", parse_mode="MarkdownV2")
        return

    username_or_id = first_line[1]
    duration = parse_duration(first_line[2]) if len(first_line) > 2 else DEFAULT_MUTE_DURATION
    reason = escape_markdown(text_lines[1])

    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)
    if not user_id:
        await message.reply(INVALID_USER_ERROR, parse_mode="MarkdownV2")
        return

    mention = await get_mention(bot, chat_id, user_id)

    if user_id == moderator_id:
        await message.reply(SELF_MUTE_ERROR, parse_mode="MarkdownV2")
        return

    if user_id == bot.id:
        await message.reply(BOT_MUTE_ERROR, parse_mode="MarkdownV2")
        return

    # Проверяем, является ли пользователь админом или владельцем
    is_admin, is_owner = await is_target_admin_or_owner(bot, chat_id, user_id)
    if is_owner:
        await message.reply(MUTE_OWNER_ERROR, parse_mode="MarkdownV2")
        return
    if is_admin:
        await message.reply(MUTE_ADMIN_ERROR, parse_mode="MarkdownV2")
        return

    success = await mute_user(bot, chat_id, user_id, mention, duration, moderator_id, reason)

    if success:
        duration_text = f" на {duration // 3600} ч\\." if duration < 86400 else f" на {duration // 86400} дн\\."
        await message.answer(f"🔇 *{mention} получил мут{duration_text}*\n📌 *Причина:* {reason}", parse_mode="MarkdownV2")
    else:
        await message.reply(MUTE_FAILED_ERROR, parse_mode="MarkdownV2")

@mute_router.message(Command("dmute"))
async def cmd_dmute(message: types.Message, bot: Bot):
    """📌 Команда для мута с удалением сообщения, на которое ответили."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Проверяем, что чат — супергруппа
    if message.chat.type != "supergroup":
        await message.reply(MUTE_NOT_SUPERGROUP, parse_mode="MarkdownV2")
        return

    if not message.reply_to_message:
        await message.reply(DMUTE_REPLY_ERROR, parse_mode="MarkdownV2")
        return

    user_id = message.reply_to_message.from_user.id
    mention = await get_mention(bot, chat_id, user_id)

    text_lines = message.text.strip().split("\n", 1)
    if len(text_lines) < 2:
        await message.reply(INVALID_DMUTE_INPUT_ERROR, parse_mode="MarkdownV2")
        return

    first_line = text_lines[0].split(maxsplit=1)
    duration = parse_duration(first_line[1]) if len(first_line) > 1 else DEFAULT_MUTE_DURATION
    reason = escape_markdown(text_lines[1])

    if user_id == moderator_id:
        await message.reply(SELF_MUTE_ERROR, parse_mode="MarkdownV2")
        return

    if user_id == bot.id:
        await message.reply(BOT_MUTE_ERROR, parse_mode="MarkdownV2")
        return

    # Проверяем, является ли пользователь админом или владельцем
    is_admin, is_owner = await is_target_admin_or_owner(bot, chat_id, user_id)
    if is_owner:
        await message.reply(MUTE_OWNER_ERROR, parse_mode="MarkdownV2")
        return
    if is_admin:
        await message.reply(MUTE_ADMIN_ERROR, parse_mode="MarkdownV2")
        return

    deleted = await delete_message_safe(bot, chat_id, message.reply_to_message.message_id)

    success = await mute_user(bot, chat_id, user_id, mention, duration, moderator_id, reason)

    if success:
        duration_text = f" на {duration // 3600} ч\\." if duration < 86400 else f" на {duration // 86400} дн\\."
        delete_text = " и сообщение удалено" if deleted else " (сообщение не удалено — нет прав)"
        await message.answer(f"🔇 *{mention} получил мут{duration_text}*{delete_text}\n📌 *Причина:* {reason}", 
                             parse_mode="MarkdownV2")
    else:
        await message.reply(MUTE_FAILED_ERROR, parse_mode="MarkdownV2")

@mute_router.message(Command("unmute"))
async def cmd_unmute(message: types.Message, bot: Bot):
    """📌 Команда для снятия мута вручную."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Проверяем, что чат — супергруппа
    if message.chat.type != "supergroup":
        await message.reply(MUTE_NOT_SUPERGROUP, parse_mode="MarkdownV2")
        return

    user_id = None
    username_or_id = None

    # Проверяем, есть ли ответ на сообщение
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
        username_or_id = message.reply_to_message.from_user.username
    else:
        # Проверяем аргументы команды
        if len(message.text.split()) > 1:
            username_or_id = message.text.split()[-1]
            user_id = await get_user_id_by_username(bot, chat_id, username_or_id)

    if not user_id:
        await message.reply(UNMUTE_INVALID_USER_ERROR, parse_mode="MarkdownV2")
        return

    success = await unmute_user(bot, chat_id, user_id)

    if success:
        mention = await get_mention(bot, chat_id, user_id)
        await message.reply(f"✅ *Мут с {mention} снят\\!*", parse_mode="MarkdownV2")
    else:
        await message.reply(UNMUTE_FAILED_ERROR, parse_mode="MarkdownV2")

async def mute_user(bot: Bot, chat_id: int, user_id: int, mention: str, duration: int, moderator_id: int, reason: str) -> bool:
    """🚫 Выдача мута пользователю на заданное время."""
    until_time = int(time.time()) + duration
    db = await db_instance.get_connection()
    try:
        await db.execute("""
            INSERT INTO moderation (chat_id, user_id, mute_until, timestamp, reason, moderator_id)
            VALUES (?, ?, ?, ?, ?, ?) 
            ON CONFLICT(chat_id, user_id) DO UPDATE SET mute_until = ?, timestamp = ?, reason = ?, moderator_id = ?
        """, (chat_id, user_id, until_time, int(time.time()), reason, moderator_id,
              until_time, int(time.time()), reason, moderator_id))
        await db.commit()
    except Exception as e:
        logging.error(f"❌ Ошибка при добавлении мута для пользователя {user_id}: {e}")
        return False
    finally:
        await db.close()

    try:
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(), until_date=until_time)
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при муте пользователя {user_id}: {e}")
        return False

async def unmute_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """✅ Снимает мут с пользователя и обновляет БД."""
    db = await db_instance.get_connection()
    try:
        await db.execute("UPDATE moderation SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()
    except Exception as e:
        logging.error(f"❌ Ошибка при снятии мута с пользователя {user_id}: {e}")
        return False
    finally:
        await db.close()

    try:
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        ))
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при снятии мута с пользователя {user_id}: {e}")
        return False