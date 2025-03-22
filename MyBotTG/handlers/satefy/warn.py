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
warn_router = Router()

# 🔴 Настройки варнов
WARN_LIMIT = 3  # Лимит варнов перед мутом
MUTE_DURATION = 7 * 24 * 60 * 60  # Мут на 7 дней
WARN_EXPIRE = 7 * 24 * 60 * 60  # Варн истекает через 7 дней


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)


async def get_user_id_from_message(message: types.Message, bot: Bot) -> tuple[int, str]:
    """Определяет user_id и корректное MarkdownV2-упоминание пользователя."""
    args = message.text.split(maxsplit=2)

    if message.reply_to_message:
        user = message.reply_to_message.from_user
        user_name = escape_markdown(user.full_name or user.username or "Пользователь")
        mention = f"[{user_name}](tg://user?id={user.id})"
        return user.id, mention

    if len(args) > 1:
        if args[1].isdigit():
            return int(args[1]), f"[Пользователь](tg://user?id={args[1]})"
        elif args[1].startswith("@"):
            user_id = await get_user_id_by_username(bot, message.chat.id, args[1])
            if user_id:
                user = await bot.get_chat_member(message.chat.id, user_id)  # Получаем данные пользователя
                user_name = escape_markdown(user.user.full_name or args[1])  # Используем имя, если оно есть
                return user_id, f"[{user_name}](tg://user?id={user_id})"

    return None, None


@warn_router.message(Command("warn"))
async def cmd_warn(message: types.Message, bot: Bot):
    """📌 Команда для выдачи варна."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id
    user_id, mention = await get_user_id_from_message(message, bot)

    if not user_id:
        await message.reply("⚠️ *Ошибка:* Укажите ID или username пользователя, либо ответьте на его сообщение.", parse_mode="MarkdownV2")
        return

    if user_id == moderator_id:
        await message.reply("❌ *Вы не можете выдать варн самому себе!*", parse_mode="MarkdownV2")
        return

    if user_id == bot.id:
        await message.reply("🤖 *Ботам нельзя выдавать варны!*", parse_mode="MarkdownV2")
        return

    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        await asyncio.sleep(0.1)  # Задержка после запроса
    except TelegramAPIError:
        await message.reply("❌ *Ошибка:* Не удалось получить данные пользователя.", parse_mode="MarkdownV2")
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await message.reply("👑 *Ошибка:* Нельзя выдавать варны владельцу чата!", parse_mode="MarkdownV2")
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await message.reply("🛡 *Ошибка:* Нельзя выдавать варны администраторам!", parse_mode="MarkdownV2")
        return

    args = message.text.split(maxsplit=2)
    reason = escape_markdown(args[2] if len(args) > 2 else "🚨 Без указания причины")

    warns = await warn_user(chat_id, user_id, moderator_id, reason)

    if warns >= WARN_LIMIT:
        await mute_user(bot, chat_id, user_id, mention)
        await message.answer(f"🚫 *{mention} получил {warns} варна и теперь в муте на 7 дней!*", parse_mode="MarkdownV2")
    else:
        await message.answer(f"⚠️ *{mention} получил варн\\!*\n📊 *Всего варнов:* {warns}/3", parse_mode="MarkdownV2")


@warn_router.message(Command("unwarn"))
async def cmd_unwarn(message: types.Message, bot: Bot):
    """📌 Команда для снятия ОДНОГО варна."""
    chat_id = message.chat.id
    user_id, mention = await get_user_id_from_message(message, bot)

    if not user_id:
        await message.reply("⚠️ *Ошибка:* Укажите ID или username пользователя, либо ответьте на его сообщение\\.", parse_mode="MarkdownV2")
        return

    warns = await get_active_warns(chat_id, user_id)
    if warns == 0:
        await message.reply(f"✅ *У {mention} нет активных варнов\\.*", parse_mode="MarkdownV2")
        return

    await remove_warn(chat_id, user_id)
    warns -= 1

    await message.reply(f"✅ *Снят 1 варн у {mention}\\.*\n📊 *Осталось варнов:* {warns}/3", parse_mode="MarkdownV2")


async def warn_user(chat_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """✅ Выдаёт варн пользователю и записывает его в БД."""
    expire_at = int(time.time()) + WARN_EXPIRE
    db = await db_instance.get_connection()

    await db.execute("""
        INSERT INTO warns_log (chat_id, user_id, reason, moderator_id, timestamp, expire_at) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, reason, moderator_id, int(time.time()), expire_at))
    await db.commit()

    return await get_active_warns(chat_id, user_id)


async def remove_warn(chat_id: int, user_id: int):
    """🗑 Удаляет один варн (самый старый)."""
    db = await db_instance.get_connection()
    await db.execute("""
        DELETE FROM warns_log 
        WHERE rowid = (
            SELECT rowid FROM warns_log 
            WHERE chat_id = ? AND user_id = ? 
            ORDER BY timestamp ASC LIMIT 1
        )
    """, (chat_id, user_id))
    await db.commit()


async def get_active_warns(chat_id: int, user_id: int) -> int:
    """📊 Подсчитывает только активные (не истекшие) варны."""
    await clean_expired_warns()
    db = await db_instance.get_connection()
    async with db.execute("""
        SELECT COUNT(*) FROM warns_log 
        WHERE chat_id = ? AND user_id = ? AND expire_at > ?
    """, (chat_id, user_id, int(time.time()))) as cursor:
        count = await cursor.fetchone()
    return count[0] if count else 0


async def clean_expired_warns():
    """🗑 Удаляет устаревшие варны (старше 7 дней)."""
    db = await db_instance.get_connection()
    await db.execute("DELETE FROM warns_log WHERE expire_at <= ?", (int(time.time()),))
    await db.commit()


async def mute_user(bot: Bot, chat_id: int, user_id: int, mention: str):
    """🚫 Выдаёт мут пользователю на 7 дней."""
    until_time = int(time.time()) + MUTE_DURATION
    db = await db_instance.get_connection()

    await db.execute("""
        INSERT INTO moderation (chat_id, user_id, mute_until, timestamp)
        VALUES (?, ?, ?, ?) 
        ON CONFLICT(chat_id, user_id) DO UPDATE SET mute_until = ?, timestamp = ?
    """, (chat_id, user_id, until_time, int(time.time()), until_time, int(time.time())))
    await db.commit()

    try:
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(), until_date=until_time)
        await bot.send_message(chat_id, f"🔇 *{mention} получил мут на 7 дней!*", parse_mode="MarkdownV2")
        await asyncio.sleep(0.1)  # Задержка после запроса
    except TelegramAPIError:
        logging.error(f"❌ Ошибка при муте пользователя {user_id}")