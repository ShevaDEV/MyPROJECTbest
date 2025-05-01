import logging
import re
from datetime import datetime
from aiogram import Router, types, Bot
from aiogram.filters import Command
from dabase.database import db_instance
from utils.telegram_queue import telegram_queue

logging.basicConfig(level=logging.INFO)
rules_router = Router()

# Константы для сообщений
NO_RULES_ERROR = "⚠️ *Правила чата ещё не установлены\\.*\n" \
                 "ℹ️ Администраторы могут задать их с помощью /setrules\\."
RULES_ERROR = "⚠️ *Ошибка при получении правил\\.*"
INVALID_RULES_FORMAT_ERROR = "⚠️ *Ошибка:* Укажите правила в формате:\n/setrules\n[текст правил]"
EMPTY_RULES_ERROR = "⚠️ *Ошибка:* Текст правил не может быть пустым\\. Укажите правила в формате:\n/setrules\n[текст правил]"
SET_RULES_ERROR = "⚠️ *Ошибка при установке правил\\.*"

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*[\]()~`>#+-=|{}.!])", r"\\\1", text)

@rules_router.message(Command("rules"))
async def cmd_rules(message: types.Message, bot: Bot):
    """📜 Показывает правила чата."""
    chat_id = message.chat.id

    db = await db_instance.get_connection()
    try:
        async with db.execute("SELECT rules, last_updated, moderator_id FROM chat_settings WHERE chat_id = ?", (chat_id,)) as cursor:
            result = await cursor.fetchone()

        if result and result["rules"]:
            rules_text = escape_markdown(result["rules"])
            last_updated = datetime.fromtimestamp(result["last_updated"]).strftime("%d.%m.%Y %H:%M")
            moderator_id = result["moderator_id"]
            
            try:
                moderator = await bot.get_chat_member(chat_id, moderator_id)
                moderator_mention = f"@{moderator.user.username}" if moderator.user.username else f"[ID: {moderator_id}](tg://user?id={moderator_id})"
            except Exception:
                moderator_mention = f"[ID: {moderator_id}](tg://user?id={moderator_id})"

            response = f"📜 *Правила чата*\n" \
                       f"───────────────\n" \
                       f"{rules_text}\n\n" \
                       f"⏰ *Обновлено:* {escape_markdown(last_updated)}\n" \
                       f"👤 *Автор:* {moderator_mention}"
        else:
            response = NO_RULES_ERROR

        await telegram_queue.add_request(
            lambda: message.reply(response, parse_mode="MarkdownV2")
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при получении правил для чата {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: message.reply(RULES_ERROR, parse_mode="MarkdownV2")
        )
    finally:
        await db.close()

@rules_router.message(Command("setrules"))
async def cmd_setrules(message: types.Message, bot: Bot):
    """✏️ Устанавливает или обновляет правила чата."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Логируем полный текст сообщения для отладки
    logging.info(f"Полный текст команды: {repr(message.text)}")

    # Разбиваем текст на строки
    lines = message.text.strip().split("\n")
    if len(lines) < 2:
        await telegram_queue.add_request(
            lambda: message.reply(INVALID_RULES_FORMAT_ERROR, parse_mode="MarkdownV2")
        )
        return

    # Извлекаем текст правил (всё после первой строки)
    rules_text = "\n".join(lines[1:]).strip()
    if not rules_text:
        await telegram_queue.add_request(
            lambda: message.reply(EMPTY_RULES_ERROR, parse_mode="MarkdownV2")
        )
        return

    db = await db_instance.get_connection()
    try:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, rules, last_updated, moderator_id)
            VALUES (?, ?, strftime('%s', 'now'), ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                rules = excluded.rules,
                last_updated = excluded.last_updated,
                moderator_id = excluded.moderator_id
        """, (chat_id, rules_text, moderator_id))
        await db.commit()

        last_updated = datetime.now().strftime("%d.%m.%Y %H:%M")
        try:
            moderator = await bot.get_chat_member(chat_id, moderator_id)
            moderator_mention = f"@{moderator.user.username}" if moderator.user.username else f"[ID: {moderator_id}](tg://user?id={moderator_id})"
        except Exception:
            moderator_mention = f"[ID: {moderator_id}](tg://user?id={moderator_id})"

        logging.info(f"✅ Правила обновлены для чата {chat_id} модератором {moderator_id}")
        response = f"✅ *Правила чата обновлены\\!*\n" \
                   f"───────────────\n" \
                   f"{escape_markdown(rules_text)}\n\n" \
                   f"⏰ *Обновлено:* {escape_markdown(last_updated)}\n" \
                   f"👤 *Автор:* {moderator_mention}"
        
        await telegram_queue.add_request(
            lambda: message.reply(response, parse_mode="MarkdownV2")
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при установке правил для чата {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: message.reply(SET_RULES_ERROR, parse_mode="MarkdownV2")
        )
    finally:
        await db.close()