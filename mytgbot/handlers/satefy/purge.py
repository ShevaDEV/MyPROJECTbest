import logging
import time
import re
import asyncio
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance
from handlers.satefy.user_utils import get_user_id_by_username
from utils.telegram_queue import telegram_queue

logging.basicConfig(level=logging.INFO)
purge_router = Router()

# Константы для сообщений
ADMIN_ONLY_ERROR = "🚫 *Ошибка:* Эта команда доступна только администраторам и владельцу чата\\."
BOT_NO_DELETE_PERMS_ERROR = "🚫 *Ошибка:* У бота нет прав на удаление сообщений в этом чате\\. Дайте мне права администратора с возможностью удалять сообщения\\."
INVALID_PURGE_ARGS_ERROR = "⚠️ *Ошибка:* Укажите аргументы\\. Формат: \n" \
                          "• /purge N — удалить N последних сообщений в чате\n" \
                          "• /purge @username — удалить все сообщения пользователя за период\n" \
                          "• /purge @username N — удалить N сообщений пользователя за период"
INVALID_USER_ERROR = "⚠️ *Ошибка:* Пользователь не найден\\."
INVALID_LIMIT_ERROR = "⚠️ *Ошибка:* Количество сообщений должно быть больше 0\\."
NO_PURGE_PERIOD_ERROR = "⚠️ *Ошибка:* Период очистки не установлен\\. Используйте /setpurgeperiod для настройки\\."
NO_MESSAGES_FOUND = "🧹 *Сообщений для удаления не найдено\\.*"
PURGE_ERROR = "⚠️ *Ошибка при очистке сообщений\\.*"
INVALID_PERIOD_ARGS_ERROR = "⚠️ *Ошибка:* Укажите период\\. Формат: /setpurgeperiod [время] \\(например, 1h, 12h, 2d\\)"
INVALID_PERIOD_RANGE_ERROR = "⚠️ *Ошибка:* Укажите период от 1s до 48h\\. Например, 1h, 12h, 1d\\."
SET_PERIOD_ERROR = "⚠️ *Ошибка при установке периода\\.*"

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*[\]()~`>#+-=|{}.!])", r"\\\1", text)

def parse_duration(duration_str: str) -> int:
    """Парсит длительность (например, '2h' -> 7200 секунд)."""
    match = re.match(r"(\d+)([smhd])", duration_str.lower())
    if not match:
        return 0
    value, unit = int(match.group(1)), match.group(2)
    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    return 0

def format_period(seconds: int) -> str:
    """Форматирует период в читаемый вид (например, '15 минут', '1 час', '2 дня')."""
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} минут" if minutes != 1 else "1 минута"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} часов" if hours != 1 else "1 час"
    else:
        days = seconds // 86400
        return f"{days} дней" if days != 1 else "1 день"

async def get_mention(bot: Bot, chat_id: int, user_id: int) -> str:
    """🔍 Получает упоминание пользователя (username или full_name)."""
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        if chat_member.user.username:
            return f"@{chat_member.user.username}"
        return f"[{escape_markdown(chat_member.user.full_name)}](tg://user?id={user_id})"
    except TelegramAPIError:
        return f"[Пользователь](tg://user?id={user_id})"

async def get_purge_period(chat_id: int) -> int:
    """Получает период очистки для чата из chat_settings."""
    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT purge_period FROM chat_settings WHERE chat_id = ?", (chat_id,)) as cursor:
            result = await cursor.fetchone()
        period = result["purge_period"] if result else 0
        logging.info(f"📏 Период очистки для чата {chat_id}: {period} секунд")
        return period
    except Exception as e:
        logging.error(f"❌ Ошибка при получении периода очистки для чата {chat_id}: {e}")
        return 0
    finally:
        await db.close()

async def can_delete_messages(bot: Bot, chat_id: int) -> bool:
    """Проверяет, может ли бот удалять сообщения в чате."""
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        can_delete = isinstance(bot_member, types.ChatMemberAdministrator) and bot_member.can_delete_messages
        logging.info(f"🔍 Права бота в чате {chat_id}: can_delete_messages={can_delete}")
        return can_delete
    except TelegramAPIError as e:
        logging.error(f"❌ Ошибка при проверке прав бота в чате {chat_id}: {e}")
        return False

@purge_router.message(Command("purge"))
async def cmd_purge(message: types.Message, bot: Bot):
    """🧹 Удаляет сообщения в чате и через 5 секунд удаляет саму команду."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id
    command_message_id = message.message_id

    if not await can_delete_messages(bot, chat_id):
        await telegram_queue.add_request(
            lambda: message.reply(BOT_NO_DELETE_PERMS_ERROR, parse_mode="MarkdownV2")
        )
        return

    args = message.text.strip().split(maxsplit=2)
    if len(args) < 2:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_PURGE_ARGS_ERROR, parse_mode="MarkdownV2")
        )
        return

    user_id = None
    limit = None
    use_period = False

    if args[1].startswith("@"):
        user_id = await get_user_id_by_username(bot, chat_id, args[1])
        if not user_id:
            await telegram_queue.add_request(
                lambda: message.reply(INVALID_USER_ERROR, parse_mode="MarkdownV2")
            )
            return
        limit = int(args[2]) if len(args) > 2 and args[2].isdigit() else None
        use_period = True
    elif args[1].isdigit():
        limit = int(args[1])
        if len(args) > 2 and args[2].startswith("@"):
            user_id = await get_user_id_by_username(bot, chat_id, args[2])
            if not user_id:
                await telegram_queue.add_request(
                    lambda: message.reply(INVALID_USER_ERROR, parse_mode="MarkdownV2")
                )
                return
            use_period = True
    else:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_PURGE_ARGS_ERROR, parse_mode="MarkdownV2")
        )
        return

    if limit and limit <= 0:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_LIMIT_ERROR, parse_mode="MarkdownV2")
        )
        return

    purge_period = await get_purge_period(chat_id) if use_period else None
    if use_period and purge_period == 0:
        await telegram_queue.add_request(
            lambda: message.reply(NO_PURGE_PERIOD_ERROR, parse_mode="MarkdownV2")
        )
        return

    time_limit = int(time.time()) - purge_period if use_period else None
    logging.info(f"⏳ Time limit для чата {chat_id}: {time_limit if use_period else 'не используется'} (текущее время: {int(time.time())})")

    db = await db_instance.get_connection()
    try:
        if user_id:
            query = "SELECT message_id, timestamp FROM messages WHERE chat_id = ? AND user_id = ?"
            params = (chat_id, user_id)
            if use_period:
                query += " AND timestamp >= ?"
                params = (chat_id, user_id, time_limit)
            if limit:
                query += " ORDER BY timestamp DESC LIMIT ?"
                params = params + (limit,)
            
            async with db.execute(query, params) as cursor:
                messages = await cursor.fetchall()
            
            mention = await get_mention(bot, chat_id, user_id)
        else:
            query = "SELECT message_id, timestamp FROM messages WHERE chat_id = ? ORDER BY timestamp DESC LIMIT ?"
            async with db.execute(query, (chat_id, limit)) as cursor:
                messages = await cursor.fetchall()
            mention = None

        logging.info(f"📋 Найдено сообщений для удаления: {len(messages)} в чате {chat_id}")
        if messages:
            for msg in messages:
                logging.info(f"Сообщение {msg['message_id']} с timestamp {msg['timestamp']}")

        if not messages:
            period_text = format_period(purge_period) if use_period else None
            response = NO_MESSAGES_FOUND + \
                       (f"\n⏳ *Период:* последние {escape_markdown(period_text)}" if use_period else "") + \
                       (f"\n👤 {mention}" if mention else "")
            await telegram_queue.add_request(
                lambda: message.reply(response, parse_mode="MarkdownV2")
            )
            return

        deleted_count = 0
        failed_count = 0
        for msg in messages:
            try:
                logging.info(f"Попытка удалить сообщение {msg['message_id']} из чата {chat_id}")
                await telegram_queue.add_request(
                    lambda: bot.delete_message(chat_id, msg["message_id"])
                )
                deleted_count += 1
                await db.execute("DELETE FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, msg["message_id"]))
                logging.info(f"✅ Сообщение {msg['message_id']} успешно удалено")
            except TelegramAPIError as e:
                logging.error(f"❌ Ошибка при удалении сообщения {msg['message_id']}: {e}")
                failed_count += 1
                if "message to delete not found" in str(e):
                    await db.execute("DELETE FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, msg["message_id"]))
                continue

        await db.commit()

        # Формируем отчёт
        executor_mention = await get_mention(bot, chat_id, moderator_id)
        period_text = format_period(purge_period) if use_period else None
        if user_id and user_id != moderator_id:
            response = f"🧹 *Сообщения пользователя удалены\\!*\n" \
                       f"───────────────\n" \
                       f"👤 {mention}\n" \
                       f"🗑 *Удалено:* {deleted_count} сообщений" + \
                       (f"\n⚠️ *Не удалось удалить:* {failed_count} сообщений" if failed_count > 0 else "") + \
                       (f"\n⏳ *Период:* последние {escape_markdown(period_text)}" if use_period else "") + \
                       f"\n👨‍💻 *Исполнитель:* {executor_mention}"
        else:
            response = f"🧹 *Чат очищен\\!*\n" \
                       f"───────────────\n" \
                       f"🗑 *Удалено:* {deleted_count} сообщений" + \
                       (f"\n⚠️ *Не удалось удалить:* {failed_count} сообщений" if failed_count > 0 else "") + \
                       (f"\n⏳ *Период:* последние {escape_markdown(period_text)}" if use_period else "") + \
                       f"\n👨‍💻 *Исполнитель:* {executor_mention}"

        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, response, parse_mode="MarkdownV2")
        )

        # Ждём 5 секунд и удаляем сообщение с командой
        await asyncio.sleep(5)
        try:
            await bot.delete_message(chat_id, command_message_id)
            logging.info(f"✅ Команда {command_message_id} удалена")
        except TelegramAPIError as e:
            logging.error(f"❌ Ошибка при удалении команды {command_message_id}: {e}")

    except Exception as e:
        logging.error(f"❌ Ошибка при выполнении purge в чате {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: message.reply(PURGE_ERROR, parse_mode="MarkdownV2")
        )
    finally:
        await db.close()

@purge_router.message(Command("setpurgeperiod"))
async def cmd_set_purge_period(message: types.Message, bot: Bot):
    """⚙️ Устанавливает период очистки для команды /purge."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_PERIOD_ARGS_ERROR, parse_mode="MarkdownV2")
        )
        return

    period_str = args[1]
    period_seconds = parse_duration(period_str)
    if period_seconds <= 0 or period_seconds > 172800:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_PERIOD_RANGE_ERROR, parse_mode="MarkdownV2")
        )
        return

    db = await db_instance.get_connection()
    try:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, purge_period)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET purge_period = ?
        """, (chat_id, period_seconds, period_seconds))
        await db.commit()

        period_text = format_period(period_seconds)
        response = f"⚙️ *Период очистки установлен\\!*\n" \
                   f"───────────────\n" \
                   f"⏳ *Новый период:* {escape_markdown(period_text)}\n" \
                   f"👤 *Установил:* {escape_markdown(f'@{message.from_user.username}' if message.from_user.username else str(moderator_id))}"
        
        await telegram_queue.add_request(
            lambda: message.reply(response, parse_mode="MarkdownV2")
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при установке периода очистки для чата {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: message.reply(SET_PERIOD_ERROR, parse_mode="MarkdownV2")
        )
    finally:
        await db.close()