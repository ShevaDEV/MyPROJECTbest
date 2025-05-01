import logging
import re
import time
import asyncio
from datetime import datetime
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dabase.database import db_instance
from handlers.satefy.user_utils import get_user_id_by_username
from utils.telegram_queue import telegram_queue

logging.basicConfig(level=logging.INFO)
ban_router = Router()

# Константы для сообщений
ADMIN_ONLY_ERROR = "🚫 *Ошибка:* Эта команда доступна только администраторам и владельцу чата\\."
INVALID_BAN_INPUT_ERROR = "⚠️ *Ошибка:* Укажите username либо ID на первой строке и причину на второй\\."
INVALID_DBAN_INPUT_ERROR = "⚠️ *Ошибка:* Укажите время на первой строке и причину на второй\\."
INVALID_USER_ERROR = "⚠️ *Ошибка:* Не удалось найти пользователя\\."
INVALID_UNBAN_INPUT_ERROR = "⚠️ *Ошибка:* Укажите ID или username пользователя\\."
DBAN_REPLY_ERROR = "⚠️ *Ошибка:* Используйте /dban в ответ на сообщение, которое нужно удалить\\."
SELF_BAN_ERROR = "❌ *Вы не можете забанить самого себя\\!*"
BOT_BAN_ERROR = "🤖 *Ботам нельзя выдавать бан\\!*"
OWNER_BAN_ERROR = "👑 *Ошибка:* Нельзя банить владельца чата\\!"
ADMIN_BAN_ERROR = "🛡 *Ошибка:* Нельзя банить администраторов\\!"
BAN_FAILED_ERROR = "⚠️ *Ошибка:* Не удалось забанить пользователя\\."
UNBAN_FAILED_ERROR = "⚠️ *Ошибка:* Не удалось разбанить пользователя\\."
NO_BANS_MESSAGE = "✅ *В чате нет забаненных пользователей\\.*"

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

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
        await db.close()

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

@ban_router.message(Command("ban"))
async def cmd_ban(message: types.Message, bot: Bot):
    """🚫 Банит пользователя (навсегда или на указанный срок)."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    text_lines = message.text.strip().split("\n", 1)
    if len(text_lines) < 2:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_BAN_INPUT_ERROR, parse_mode="MarkdownV2")
        )
        return

    args = text_lines[0].split()
    username_or_id = args[1]
    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)

    if not user_id:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_USER_ERROR, parse_mode="MarkdownV2")
        )
        return

    try:
        chat_member = await telegram_queue.add_request(
            lambda: bot.get_chat_member(chat_id, user_id)
        )
        mention = f"@{chat_member.user.username}" if chat_member.user.username else f"[{chat_member.user.full_name}](tg://user?id={user_id})"
    except TelegramAPIError:
        mention = f"[Пользователь](tg://user?id={user_id})"

    if user_id == moderator_id:
        await telegram_queue.add_request(
            lambda: message.reply(SELF_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    if user_id == bot.id:
        await telegram_queue.add_request(
            lambda: message.reply(BOT_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await telegram_queue.add_request(
            lambda: message.reply(OWNER_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await telegram_queue.add_request(
            lambda: message.reply(ADMIN_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    ban_days = 0
    if len(args) > 2:
        match = re.match(r"(\d+)[дd]", args[2], re.IGNORECASE)
        if match:
            ban_days = int(match.group(1))

    reason = escape_markdown(text_lines[1])
    success = await ban_user(bot, chat_id, user_id, mention, moderator_id, reason, ban_days)

    if success:
        duration_text = f" на {ban_days} дн." if ban_days > 0 else " навсегда"
        await telegram_queue.add_request(
            lambda: message.answer(f"🚫 *{mention} забанен{duration_text}*\n📌 *Причина:* {reason}", parse_mode="MarkdownV2")
        )
    else:
        await telegram_queue.add_request(
            lambda: message.reply(BAN_FAILED_ERROR, parse_mode="MarkdownV2")
        )

@ban_router.message(Command("dban"))
async def cmd_dban(message: types.Message, bot: Bot):
    """🚫 Банит пользователя с удалением сообщения, на которое ответили."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    if not message.reply_to_message:
        await telegram_queue.add_request(
            lambda: message.reply(DBAN_REPLY_ERROR, parse_mode="MarkdownV2")
        )
        return

    user_id = message.reply_to_message.from_user.id
    try:
        chat_member = await telegram_queue.add_request(
            lambda: bot.get_chat_member(chat_id, user_id)
        )
        mention = f"@{chat_member.user.username}" if chat_member.user.username else f"[{chat_member.user.full_name}](tg://user?id={user_id})"
    except TelegramAPIError:
        mention = f"[Пользователь](tg://user?id={user_id})"

    text_lines = message.text.strip().split("\n", 1)
    if len(text_lines) < 2:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_DBAN_INPUT_ERROR, parse_mode="MarkdownV2")
        )
        return

    args = text_lines[0].split()
    ban_days = 0
    if len(args) > 1:
        match = re.match(r"(\d+)[дd]", args[1], re.IGNORECASE)
        if match:
            ban_days = int(match.group(1))

    reason = escape_markdown(text_lines[1])

    if user_id == moderator_id:
        await telegram_queue.add_request(
            lambda: message.reply(SELF_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    if user_id == bot.id:
        await telegram_queue.add_request(
            lambda: message.reply(BOT_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await telegram_queue.add_request(
            lambda: message.reply(OWNER_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await telegram_queue.add_request(
            lambda: message.reply(ADMIN_BAN_ERROR, parse_mode="MarkdownV2")
        )
        return

    deleted = await delete_message_safe(bot, chat_id, message.reply_to_message.message_id)

    success = await ban_user(bot, chat_id, user_id, mention, moderator_id, reason, ban_days)

    if success:
        duration_text = f" на {ban_days} дн." if ban_days > 0 else " навсегда"
        delete_text = " и сообщение удалено" if deleted else " (сообщение не удалено — нет прав)"
        await telegram_queue.add_request(
            lambda: message.answer(f"🚫 *{mention} забанен{duration_text}*{delete_text}\n📌 *Причина:* {reason}", 
                                   parse_mode="MarkdownV2")
        )
    else:
        await telegram_queue.add_request(
            lambda: message.reply(BAN_FAILED_ERROR, parse_mode="MarkdownV2")
        )

@ban_router.message(Command("unban"))
async def cmd_unban(message: types.Message, bot: Bot):
    """✅ Разбанивает пользователя."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    args = message.text.split()
    if len(args) < 2:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_UNBAN_INPUT_ERROR, parse_mode="MarkdownV2")
        )
        return

    username_or_id = args[1]
    user_id = await get_user_id_by_username(bot, chat_id, username_or_id)
    if not user_id:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_USER_ERROR, parse_mode="MarkdownV2")
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
            lambda: message.reply(UNBAN_FAILED_ERROR, parse_mode="MarkdownV2")
        )

@ban_router.message(Command("banlist"))
async def cmd_banlist(message: types.Message, bot: Bot):
    """📜 Показывает список забаненных пользователей с пагинацией."""
    chat_id = message.chat.id
    page = int(message.text.split()[-1]) if len(message.text.split()) > 1 and message.text.split()[-1].isdigit() else 1
    await show_banlist(bot, chat_id, page, message.message_id)

@ban_router.callback_query(lambda c: c.data.startswith("banlist_"))
async def process_banlist_callback(callback: types.CallbackQuery, bot: Bot):
    """Обрабатывает нажатия на кнопки пагинации."""
    chat_id = int(callback.data.split("_")[2])
    page = int(callback.data.split("_")[3])
    await show_banlist(bot, chat_id, page, callback.message.message_id, callback.id)

async def show_banlist(bot: Bot, chat_id: int, page: int, message_id: int, callback_id: str = None):
    """Отображает страницу списка забаненных с кнопками."""
    bans = await get_banned_users(chat_id)
    if not bans:
        text = NO_BANS_MESSAGE
        if callback_id:
            await bot.edit_message_text(text, chat_id, message_id, parse_mode="MarkdownV2")
            await bot.answer_callback_query(callback_id)
        else:
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, text, parse_mode="MarkdownV2")
            )
        return

    total_bans = len(bans)
    total_pages = (total_bans + 9) // 10
    page = max(1, min(page, total_pages))

    start = (page - 1) * 10
    end = min(start + 10, total_bans)
    response = f"📜 *Список забаненных в чате (Страница {page}/{total_pages}):*\n"
    
    for i, ban in enumerate(bans[start:end], start + 1):
        user_id = ban['user_id']
        try:
            user = await telegram_queue.add_request(
                lambda: bot.get_chat_member(chat_id, user_id)
            )
            mention = f"@{user.user.username}" if user.user.username else f"[ID: {user_id}]"
        except TelegramAPIError:
            mention = f"[ID: {user_id}]"
        
        mod_id = ban['moderator_id']
        try:
            mod = await telegram_queue.add_request(
                lambda: bot.get_chat_member(chat_id, mod_id)
            )
            mod_mention = f"@{mod.user.username}" if mod.user.username else f"[ID: {mod_id}]"
        except TelegramAPIError:
            mod_mention = f"[ID: {mod_id}]"
        
        reason = ban['reason'] if ban['reason'] else "Причина не указана"
        timestamp = datetime.fromtimestamp(ban['timestamp']).strftime("%d.%m.%Y %H:%M")
        response += f"{i}\\. {mention}\n" \
                    f"   *Причина:* {escape_markdown(reason)}\n" \
                    f"   *Выдал:* {mod_mention}\n" \
                    f"   *Когда:* {timestamp}\n"

    response += f"*Всего забанено:* {total_bans}"

    prev_page = total_pages if page == 1 else page - 1
    next_page = 1 if page == total_pages else page + 1
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Назад", callback_data=f"banlist_prev_{chat_id}_{prev_page}"),
            InlineKeyboardButton(text="Вперёд", callback_data=f"banlist_next_{chat_id}_{next_page}")
        ]
    ])

    if callback_id:
        await bot.edit_message_text(response, chat_id, message_id, reply_markup=keyboard, parse_mode="MarkdownV2")
        await bot.answer_callback_query(callback_id)
    else:
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, response, reply_markup=keyboard, parse_mode="MarkdownV2")
        )

async def ban_user(bot: Bot, chat_id: int, user_id: int, mention: str, moderator_id: int, reason: str, days: int) -> bool:
    """🚫 Добавляет бан пользователя в БД и в Telegram."""
    db = await db_instance.get_connection()
    try:
        current_time = int(time.time())
        ban_until = current_time + days * 86400 if days > 0 else 0

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
    except Exception as e:
        logging.error(f"❌ Ошибка при добавлении бана для пользователя {user_id}: {e}")
        return False
    finally:
        await db.close()

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
    except Exception as e:
        logging.error(f"❌ Ошибка при снятии бана с пользователя {user_id}: {e}")
        return False
    finally:
        await db.close()

    try:
        await telegram_queue.add_request(
            lambda: bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        )
        return True
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при разбане пользователя {user_id}: {e}")
        return False

async def get_banned_users(chat_id: int) -> list:
    """Получает список забаненных пользователей."""
    db = await db_instance.get_connection()
    try:
        async with db.execute("""
            SELECT user_id, reason, moderator_id, timestamp 
            FROM moderation 
            WHERE chat_id = ? AND ban_status = 1 
            ORDER BY timestamp ASC
        """, (chat_id,)) as cursor:
            return await cursor.fetchall()
    except Exception as e:
        logging.error(f"❌ Ошибка при получении списка забаненных в чате {chat_id}: {e}")
        return []
    finally:
        await db.close()