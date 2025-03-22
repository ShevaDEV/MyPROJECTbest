import logging
import re
import time
import asyncio
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance
from handlers.satefy.user_utils import get_user_id_by_username
from utils.telegram_queue import telegram_queue  # Импортируем очередь

logging.basicConfig(level=logging.INFO)
ban_router = Router()


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~>#+\-=|{}.!])", r"\\\1", text)


async def check_and_remove_ban(bot: Bot):
    """🔍 Проверяет истёк ли бан и снимает его."""
    now = int(time.time())
    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT chat_id, user_id FROM moderation WHERE ban_until > 0 AND ban_until <= ?", (now,)) as cursor:
            expired_bans = await cursor.fetchall()

        for chat_id, user_id in expired_bans:
            await unban_user(bot, chat_id, user_id)
    finally:
        await db.close()  # ✅ Закрываем соединение с БД


@ban_router.message(Command("ban"))
async def cmd_ban(message: types.Message, bot: Bot):
    """🚫 Банит пользователя (навсегда или на указанный срок)."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id
    text_lines = message.text.strip().split("\n", 1)  # Разбиваем текст на 2 строки

    if len(text_lines) < 2:
        await telegram_queue.add_request(
            lambda: message.reply("⚠️ *Ошибка:* Укажите пользователя на первой строке и причину на второй.", parse_mode="MarkdownV2")
        )
        return

    args = text_lines[0].split()  # Первая строка содержит имя пользователя и срок бана (если указан)
    username_or_id = args[1]  # Имя пользователя или ID
    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)

    if not user_id:
        await telegram_queue.add_request(
            lambda: message.reply("⚠️ *Ошибка:* Не удалось найти пользователя.", parse_mode="MarkdownV2")
        )
        return

    # ✅ Получаем корректное упоминание пользователя
    try:
        chat_member = await telegram_queue.add_request(
            lambda: bot.get_chat_member(chat_id, user_id)
        )
        mention = f"@{chat_member.user.username}" if chat_member.user.username else f"[{chat_member.user.full_name}](tg://user?id={user_id})"
    except TelegramAPIError:
        mention = f"[Пользователь](tg://user?id={user_id})"

    # ❌ Запрещаем банить себя, бота, владельца чата и админов
    if user_id == moderator_id:
        await telegram_queue.add_request(
            lambda: message.reply("❌ *Вы не можете забанить самого себя!*", parse_mode="MarkdownV2")
        )
        return

    if user_id == bot.id:
        await telegram_queue.add_request(
            lambda: message.reply("🤖 *Ботам нельзя выдавать бан!*", parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await telegram_queue.add_request(
            lambda: message.reply("👑 *Ошибка:* Нельзя банить владельца чата!", parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await telegram_queue.add_request(
            lambda: message.reply("🛡 *Ошибка:* Нельзя банить администраторов!", parse_mode="MarkdownV2")
        )
        return

    # ✅ Определяем срок бана
    ban_days = 0  # По умолчанию бан навсегда
    if len(args) > 2:
        match = re.match(r"(\d+)[дd]", args[2], re.IGNORECASE)
        if match:
            ban_days = int(match.group(1))

    # ✅ Определяем причину
    reason = escape_markdown(text_lines[1])

    # ✅ Баним пользователя
    success = await ban_user(bot, chat_id, user_id, mention, moderator_id, reason, ban_days)

    if success:
        duration_text = f" на {ban_days} дн." if ban_days > 0 else " навсегда"
        await telegram_queue.add_request(
            lambda: message.answer(f"🚫 *{mention} забанен{duration_text}*\n📌 *Причина:* {reason}", parse_mode="MarkdownV2")
        )
    else:
        await telegram_queue.add_request(
            lambda: message.reply("⚠️ *Ошибка:* Не удалось забанить пользователя.", parse_mode="MarkdownV2")
        )


@ban_router.message(Command("unban"))
async def cmd_unban(message: types.Message, bot: Bot):
    """✅ Разбанивает пользователя."""
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) < 2:
        await telegram_queue.add_request(
            lambda: message.reply("⚠️ *Ошибка:* Укажите ID или username пользователя.", parse_mode="MarkdownV2")
        )
        return

    username_or_id = args[1]
    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)
    if not user_id:
        await telegram_queue.add_request(
            lambda: message.reply("⚠️ *Ошибка:* Не удалось найти пользователя.", parse_mode="MarkdownV2")
        )
        return

    success = await unban_user(bot, chat_id, user_id)
    mention = f"[Пользователь](tg://user?id={user_id})"

    if success:
        await telegram_queue.add_request(
            lambda: message.reply(f"✅ *Пользователь {mention} разбанен\\!*", parse_mode="MarkdownV2")
        )
    else:
        await telegram_queue.add_request(
            lambda: message.reply("⚠️ *Ошибка:* Не удалось разбанить пользователя.", parse_mode="MarkdownV2")
        )


async def ban_user(bot: Bot, chat_id: int, user_id: int, mention: str, moderator_id: int, reason: str, days: int) -> bool:
    """🚫 Добавляет бан пользователя в БД и в Telegram."""
    db = await db_instance.get_connection()
    try:
        current_time = int(time.time())
        ban_until = current_time + days * 86400 if days > 0 else 0  # Конвертируем дни в секунды

        await db.execute("""
            INSERT INTO moderation (chat_id, user_id, ban_until, ban_status, reason, moderator_id, timestamp)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET 
                ban_until = excluded.ban_until,
                ban_status = 1,
                reason = excluded.reason,
                moderator_id = excluded.moderator_id,
                timestamp = excluded.timestamp
        """, (chat_id, user_id, ban_until, reason, moderator_id, current_time))

        await db.commit()
    finally:
        await db.close()  # ✅ Закрываем соединение с БД

    try:
        await telegram_queue.add_request(
            lambda: bot.ban_chat_member(chat_id, user_id, until_date=ban_until if ban_until else None)
        )
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при бане пользователя {user_id}: {e}")
        return False


async def unban_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """✅ Снимает бан с пользователя и обновляет БД."""
    db = await db_instance.get_connection()
    try:
        await db.execute("UPDATE moderation SET ban_status = 0, ban_until = 0 WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()
    finally:
        await db.close()  # ✅ Закрываем соединение с БД

    try:
        await telegram_queue.add_request(
            lambda: bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        )
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при разбане пользователя {user_id}: {e}")
        return False