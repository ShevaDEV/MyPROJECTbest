import logging
import re
import time
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError
from handlers.satefy.user_utils import get_user_id_by_username
from utils.telegram_queue import telegram_queue

logging.basicConfig(level=logging.INFO)
kick_router = Router()

# Константы для сообщений
BOT_NOT_ADMIN_ERROR = "🔴 *Ошибка:* Бот должен быть администратором для выполнения этой команды\\!"
INVALID_INPUT_ERROR = "⚠️ *Ошибка:* Укажите username или ответьте на сообщение пользователя\\."
INVALID_USER_ERROR = "⚠️ *Ошибка:* Не удалось найти пользователя\\."
SELF_KICK_ERROR = "❌ *Вы не можете кикнуть самого себя\\!*"
BOT_KICK_ERROR = "🤖 *Ботам нельзя выдавать кик\\!*"
OWNER_KICK_ERROR = "👑 *Ошибка:* Нельзя кикнуть владельца чата\\!"
ADMIN_KICK_ERROR = "🛡 *Ошибка:* Нельзя кикнуть администраторов\\!"
USER_NOT_IN_CHAT_ERROR = "⚠️ *Ошибка:* {mention} уже не в чате\\!"
KICK_NO_ADMIN_ERROR = "🔴 *Ошибка:* Боту нужны права администратора для выполнения команды\\!"
KICK_SUPERGROUP_ONLY_ERROR = "⚠️ *Ошибка:* Команда доступна только в супергруппах\\!"
KICK_FAILED_ERROR = "⚠️ *Ошибка:* Не удалось выгнать пользователя\\."

def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*[\]()~`>#+-=|{}.!])", r"\\\1", text)

@kick_router.message(Command("kick"))
async def cmd_kick(message: types.Message, bot: Bot):
    """🚪 Выгоняет пользователя из чата (без постоянного бана)."""
    chat_id = message.chat.id
    moderator_id = message.from_user.id

    # Проверка: является ли бот администратором
    bot_member = await bot.get_chat_member(chat_id, bot.id)
    if not isinstance(bot_member, (types.ChatMemberAdministrator, types.ChatMemberOwner)):
        await telegram_queue.add_request(
            lambda: message.reply(BOT_NOT_ADMIN_ERROR, parse_mode="MarkdownV2")
        )
        return

    # Проверяем тип чата
    chat = await bot.get_chat(chat_id)
    logging.info(f"Тип чата {chat_id}: {chat.type}")

    # Получение user_id (либо из ответа на сообщение, либо из аргумента)
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.strip().split(maxsplit=1)
        if len(args) < 2:
            await telegram_queue.add_request(
                lambda: message.reply(INVALID_INPUT_ERROR, parse_mode="MarkdownV2")
            )
            return
        
        username_or_id = args[1]
        user_id = await get_user_id_by_username(bot, chat_id, username_or_id)
        if not user_id:
            await telegram_queue.add_request(
                lambda: message.reply(INVALID_USER_ERROR, parse_mode="MarkdownV2")
            )
            return

    # Получаем информацию о пользователе
    try:
        chat_member = await telegram_queue.add_request(
            lambda: bot.get_chat_member(chat_id, user_id)
        )
        mention = f"@{chat_member.user.username}" if chat_member.user.username else f"[{escape_markdown(chat_member.user.full_name)}](tg://user?id={user_id})"
    except TelegramAPIError:
        mention = f"[Пользователь](tg://user?id={user_id})"

    # Проверки на самокик, бота и роли
    if user_id == moderator_id:
        await telegram_queue.add_request(
            lambda: message.reply(SELF_KICK_ERROR, parse_mode="MarkdownV2")
        )
        return

    if user_id == bot.id:
        await telegram_queue.add_request(
            lambda: message.reply(BOT_KICK_ERROR, parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberOwner):
        await telegram_queue.add_request(
            lambda: message.reply(OWNER_KICK_ERROR, parse_mode="MarkdownV2")
        )
        return

    if isinstance(chat_member, types.ChatMemberAdministrator) and not chat_member.user.is_bot:
        await telegram_queue.add_request(
            lambda: message.reply(ADMIN_KICK_ERROR, parse_mode="MarkdownV2")
        )
        return

    # Проверка: находится ли пользователь в чате?
    if isinstance(chat_member, (types.ChatMemberLeft, types.ChatMemberBanned)):
        await telegram_queue.add_request(
            lambda: message.reply(USER_NOT_IN_CHAT_ERROR.format(mention=mention), parse_mode="MarkdownV2")
        )
        return

    # Выполняем кик с использованием ban + unban
    try:
        logging.info(f"Попытка кикнуть пользователя {user_id} в чате {chat_id}")

        await telegram_queue.add_request(
            lambda: bot.ban_chat_member(chat_id, user_id, until_date=int(time.time() + 30))
        )
        await telegram_queue.add_request(
            lambda: bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        )

        logging.info(f"Успешно кикнут пользователь {user_id} в чате {chat_id}")
        await telegram_queue.add_request(
            lambda: message.reply(f"🚪 *{mention} выгнан из чата\\!*", parse_mode="MarkdownV2")
        )
    except TelegramAPIError as e:
        if "CHAT_ADMIN_REQUIRED" in str(e):
            error_msg = KICK_NO_ADMIN_ERROR
        elif "method is available for supergroup and channel chats only" in str(e):
            error_msg = KICK_SUPERGROUP_ONLY_ERROR
        else:
            error_msg = KICK_FAILED_ERROR

        logging.error(f"❌ Ошибка при кике пользователя {user_id} в чате {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: message.reply(error_msg, parse_mode="MarkdownV2")
        )