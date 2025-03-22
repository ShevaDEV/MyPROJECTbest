import time
import logging
import re
import asyncio
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatPermissions
from dabase.database import db_instance
from handlers.satefy.user_utils import get_user_id_by_username

logging.basicConfig(level=logging.INFO)
mute_router = Router()

# 🔴 Настройки мута
DEFAULT_MUTE_DURATION = 24 * 60 * 60  # 1 день по умолчанию


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\\\1", text)  # ✅ Экранирование всех символов


def parse_duration(duration: str) -> int:
    """🔍 Конвертирует строку (например, 3ч, 2д) в секунды."""
    match = re.match(r"(\d+)([чЧhHдДdD]?)", duration)
    if not match:
        return DEFAULT_MUTE_DURATION  # Если не указано время, ставим 24ч

    value, unit = match.groups()
    value = int(value)

    if unit.lower() in ["ч", "h"]:
        return value * 3600  # Конвертируем часы в секунды
    elif unit.lower() in ["д", "d"]:
        return value * 86400  # Конвертируем дни в секунды

    return DEFAULT_MUTE_DURATION  # Если формат неверный, 24ч по умолчанию


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
        await db.close()  # ✅ Закрываем соединение


async def get_mention(bot: Bot, chat_id: int, user_id: int) -> str:
    """🔍 Получает упоминание пользователя (username или full_name)."""
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        if chat_member.user.username:
            return f"@{chat_member.user.username}"
        return f"[{escape_markdown(chat_member.user.full_name)}](tg://user?id={user_id})"
    except TelegramAPIError:
        return f"[Пользователь](tg://user?id={user_id})"


@mute_router.message(Command("mute"))
async def cmd_mute(message: types.Message, bot: Bot):
    """📌 Команда для выдачи мута с вводом в 2 строки."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id
    text_lines = message.text.strip().split("\n", 1)  # Убираем лишние пробелы

    if len(text_lines) < 2:
        await message.reply("⚠️ *Ошибка:* Укажите пользователя и время на первой строке, а причину на второй\\.", parse_mode="MarkdownV2")
        return

    first_line = text_lines[0].split(maxsplit=2)  # Разделяем первую строку (username + время)
    if len(first_line) < 2:
        await message.reply("⚠️ *Ошибка:* Укажите username и время мута.", parse_mode="MarkdownV2")
        return

    username_or_id = first_line[1]  # Получаем имя пользователя или ID
    duration = parse_duration(first_line[2]) if len(first_line) > 2 else DEFAULT_MUTE_DURATION  # Парсим время
    reason = escape_markdown(text_lines[1])  # Вторая строка — причина

    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)
    if not user_id:
        await message.reply("⚠️ *Ошибка:* Не удалось найти пользователя.", parse_mode="MarkdownV2")
        return

    mention = await get_mention(bot, chat_id, user_id)  # ✅ Формируем корректное упоминание
    await asyncio.sleep(0.1)  # Задержка после запроса

    if user_id == moderator_id:
        await message.reply("❌ *Вы не можете замутить самого себя!*", parse_mode="MarkdownV2")
        return

    if user_id == bot.id:
        await message.reply("🤖 *Ботам нельзя выдавать мут!*", parse_mode="MarkdownV2")
        return

    success = await mute_user(bot, chat_id, user_id, mention, duration, moderator_id, reason)

    if success:
        duration_text = f" на {duration // 3600} ч\\." if duration < 86400 else f" на {duration // 86400} дн\\."
        await message.answer(f"🔇 *{mention} получил мут{duration_text}*\n📌 *Причина:* {reason}", parse_mode="MarkdownV2")
    else:
        await message.reply("⚠️ *Ошибка:* Не удалось выдать мут. Возможно, бот не является администратором.", parse_mode="MarkdownV2")


async def mute_user(bot: Bot, chat_id: int, user_id: int, mention: str, duration: int, moderator_id: int, reason: str) -> bool:
    """🚫 Выдаёт мут пользователю на заданное время."""
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
    finally:
        await db.close()  # ✅ Закрываем соединение

    try:
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(), until_date=until_time)
        await asyncio.sleep(0.1)  # Задержка после запроса
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при муте пользователя {user_id}: {e}")
        return False


@mute_router.message(Command("unmute"))
async def cmd_unmute(message: types.Message, bot: Bot):
    """📌 Команда для снятия мута вручную."""
    chat_id = message.chat.id
    username_or_id = message.text.split()[-1]

    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)
    if not user_id:
        await message.reply("⚠️ *Ошибка:* Укажите ID или username пользователя.", parse_mode="MarkdownV2")
        return

    success = await unmute_user(bot, chat_id, user_id)

    if success:
        mention = await get_mention(bot, chat_id, user_id)
        await message.reply(f"✅ *Мут с {mention} снят!*", parse_mode="MarkdownV2")
    else:
        await message.reply("⚠️ *Ошибка:* Не удалось снять мут.", parse_mode="MarkdownV2")


async def unmute_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """✅ Снимает мут с пользователя и обновляет БД."""
    db = await db_instance.get_connection()
    try:
        await db.execute("UPDATE moderation SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()
    finally:
        await db.close()  # ✅ Закрываем соединение

    try:
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        ))
        await asyncio.sleep(0.1)  # Задержка после запроса
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при снятии мута с пользователя {user_id}: {e}")
        return False