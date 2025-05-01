import logging
import time
import re
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance
from handlers.satefy.user_utils import get_mention, is_admin_or_owner  # Импорт из user_utils.py

logging.basicConfig(level=logging.INFO)
stats_router = Router()

def escape_markdown_v2(text: str) -> str:
    """Экранирование всех специальных символов для MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!<>"
    return re.sub(r"([{}])".format(re.escape(escape_chars)), r"\\\1", text)

@stats_router.message(Command("day"))
async def cmd_day(message: types.Message, bot: Bot):
    """Показывает статистику чата за текущий день."""
    chat_id = message.chat.id
    today = int(time.time() - (time.time() % 86400))  # Начало текущего дня (00:00)

    logging.info(f"Запрос /day для чата {chat_id}")

    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND timestamp >= ?", 
                              (chat_id, today)) as cursor:
            total_msgs = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE chat_id = ? AND timestamp >= ?", 
                              (chat_id, today)) as cursor:
            active_users = (await cursor.fetchone())[0]

        async with db.execute("SELECT user_id, COUNT(*) as msg_count FROM messages "
                              "WHERE chat_id = ? AND timestamp >= ? GROUP BY user_id ORDER BY msg_count DESC LIMIT 3", 
                              (chat_id, today)) as cursor:
            top_users = await cursor.fetchall()

        date_str = escape_markdown_v2(time.strftime('%d.%m.%Y'))
        response = f"*Статистика за сегодня \\({date_str}\\)*\n" \
                   f"✉️ Сообщений: {total_msgs}\n" \
                   f"👥 Активных участников: {active_users}\n"

        if top_users:
            response += "*Топ 3:*\n"
            for i, (user_id, count) in enumerate(top_users, 1):
                try:
                    mention = await get_mention(bot, chat_id, user_id)
                except TelegramAPIError:
                    mention = f"[ID: {user_id}](tg://user?id={user_id})"
                response += f"{i}\\. {mention} : {count} сообщений\n"  # Заменяем дефис на двоеточие
        else:
            response += "⚠️ Нет активности за сегодня\\.\n"

        logging.info(f"Финальное сообщение перед отправкой:\n{response}")
        await message.reply(response, parse_mode="MarkdownV2")
    except Exception as e:
        logging.error(f"Ошибка в /day для чата {chat_id}: {e}")
        await message.reply("⚠️ *Ошибка при получении статистики\\.*", parse_mode="MarkdownV2")
    finally:
        await db.close()

@stats_router.message(Command("week"))
async def cmd_week(message: types.Message, bot: Bot):
    """Показывает статистику чата за последние 7 дней."""
    chat_id = message.chat.id
    week_start = int(time.time() - (7 * 86400))

    logging.info(f"Запрос /week для чата {chat_id}")

    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND timestamp >= ?", 
                              (chat_id, week_start)) as cursor:
            total_msgs = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE chat_id = ? AND timestamp >= ?", 
                              (chat_id, week_start)) as cursor:
            active_users = (await cursor.fetchone())[0]

        async with db.execute("SELECT user_id, COUNT(*) as msg_count FROM messages "
                              "WHERE chat_id = ? AND timestamp >= ? GROUP BY user_id ORDER BY msg_count DESC LIMIT 3", 
                              (chat_id, week_start)) as cursor:
            top_users = await cursor.fetchall()

        response = "*Статистика за последние 7 дней*\n" \
                   f"✉️ Сообщений: {total_msgs}\n" \
                   f"👥 Активных участников: {active_users}\n" \
                   f"📊 Среднее в день: {total_msgs // 7 if total_msgs > 0 else 0}\n"

        if top_users:
            response += "*Топ 3:*\n"
            for i, (user_id, count) in enumerate(top_users, 1):
                try:
                    mention = await get_mention(bot, chat_id, user_id)
                except TelegramAPIError:
                    mention = f"[ID: {user_id}](tg://user?id={user_id})"
                response += f"{i}\\. {mention} : {count} сообщений\n"  # Заменяем дефис на двоеточие
        else:
            response += "⚠️ Нет активности за неделю\\.\n"

        logging.info(f"Финальное сообщение перед отправкой:\n{response}")
        await message.reply(response, parse_mode="MarkdownV2")
    except Exception as e:
        await message.reply("⚠️ *Ошибка при получении статистики\\.*", parse_mode="MarkdownV2")
        logging.error(f"Ошибка в /week для чата {chat_id}: {e}")
    finally:
        await db.close()

@stats_router.message(Command("month"))
async def cmd_month(message: types.Message, bot: Bot):
    """Показывает статистику чата за последние 30 дней."""
    chat_id = message.chat.id
    month_start = int(time.time() - (30 * 86400))

    logging.info(f"Запрос /month для чата {chat_id}")

    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND timestamp >= ?", 
                              (chat_id, month_start)) as cursor:
            total_msgs = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE chat_id = ? AND timestamp >= ?", 
                              (chat_id, month_start)) as cursor:
            active_users = (await cursor.fetchone())[0]

        async with db.execute("SELECT user_id, COUNT(*) as msg_count FROM messages "
                              "WHERE chat_id = ? AND timestamp >= ? GROUP BY user_id ORDER BY msg_count DESC LIMIT 3", 
                              (chat_id, month_start)) as cursor:
            top_users = await cursor.fetchall()

        response = "*Статистика за последние 30 дней*\n" \
                   f"✉️ Сообщений: {total_msgs}\n" \
                   f"👥 Активных участников: {active_users}\n" \
                   f"📊 Среднее в день: {total_msgs // 30 if total_msgs > 0 else 0}\n"

        if top_users:
            response += "*Топ 3:*\n"
            for i, (user_id, count) in enumerate(top_users, 1):
                try:
                    mention = await get_mention(bot, chat_id, user_id)
                except TelegramAPIError:
                    mention = f"[ID: {user_id}](tg://user?id={user_id})"
                response += f"{i}\\. {mention} : {count} сообщений\n"  # Заменяем дефис на двоеточие
        else:
            response += "⚠️ Нет активности за месяц\\.\n"

        logging.info(f"Финальное сообщение перед отправкой:\n{response}")
        await message.reply(response, parse_mode="MarkdownV2")
    except Exception as e:
        await message.reply("⚠️ *Ошибка при получении статистики\\.*", parse_mode="MarkdownV2")
        logging.error(f"Ошибка в /month для чата {chat_id}: {e}")
    finally:
        await db.close()