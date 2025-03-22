import logging
import asyncio
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance
from utils.telegram_safe_request import safe_telegram_request  # Импортируем безопасный запрос

logging.basicConfig(level=logging.INFO)
logging.getLogger('aiohttp').setLevel(logging.DEBUG)

event_router = Router()


async def save_user_to_db(chat_id: int, user: types.User, left: bool):
    """Сохраняет или обновляет информацию о пользователе в БД."""
    username = user.username if user.username else f"user_{user.id}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    logging.info(f"📌 Сохранение пользователя {user.id} (@{username}) в БД (chat_id: {chat_id}, left: {left})")

    db = await db_instance.get_connection()
    async with db:
        try:
            await db.execute("""
                INSERT INTO chat_users (user_id, chat_id, username, full_name, left)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, chat_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    left = excluded.left
            """, (user.id, chat_id, username, full_name, left))
            await db.commit()
            logging.info(f"✅ Пользователь {user.id} (@{username}) успешно сохранён")
        except Exception as e:
            logging.error(f"❌ Ошибка при сохранении пользователя {user.id}: {e}")


async def save_all_chat_members(bot: Bot, chat_id: int):
    """Синхронизирует администраторов чата через безопасные запросы Telegram API."""
    logging.info(f"📋 Начинаем синхронизацию участников чата {chat_id}...")
    try:
        # 1. Проверяем, является ли бот администратором
        try:
            bot_member = await safe_telegram_request(lambda: bot.get_chat_member(chat_id, bot.id))
        except TelegramAPIError as e:
            logging.error(f"❌ Ошибка при проверке статуса бота в чате {chat_id}: {e}")
            raise

        if bot_member.status not in ["administrator", "creator"]:
            logging.warning(f"⚠️ Бот не админ в чате {chat_id}. Ограниченная синхронизация.")
            return

        # 2. Получаем список администраторов
        try:
            chat_admins = await safe_telegram_request(lambda: bot.get_chat_administrators(chat_id))
        except TelegramAPIError as e:
            logging.error(f"❌ Ошибка при получении администраторов чата {chat_id}: {e}")
            raise

        # 3. Сохраняем администраторов в БД
        db = await db_instance.get_connection()
        async with db:
            for admin in chat_admins:
                await save_user_to_db(chat_id, admin.user, left=False)
            await db.commit()
        logging.info(f"✅ Сохранено {len(chat_admins)} администраторов.")

        logging.info("📜 Остальные участники будут добавлены через активность (track_all_messages).")

    except Exception as e:
        logging.error(f"❌ Ошибка при синхронизации чата {chat_id}: {e}")
        raise


@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=F.new_chat_member))
async def user_joined(event: ChatMemberUpdated, bot: Bot):
    """Сохранение нового участника в БД."""
    user = event.new_chat_member.user
    chat_id = event.chat.id

    if user.id == bot.id:
        logging.info(f"🤖 Бот добавлен в чат {chat_id}. Синхронизируем участников...")
        await save_all_chat_members(bot, chat_id)
    else:
        logging.info(f"✅ Новый участник: {user.id} (@{user.username})")
        await save_user_to_db(chat_id, user, left=False)


@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=F.left_chat_member))
async def user_left(event: ChatMemberUpdated):
    """Отслеживает выход участников и обновляет статус в БД."""
    user = event.old_chat_member.user
    chat_id = event.chat.id

    logging.info(f"🚪 Участник покинул чат: {user.id} (@{user.username})")
    await save_user_to_db(chat_id, user, left=True)


@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=F.is_admin()))
async def bot_became_admin(event: ChatMemberUpdated, bot: Bot):
    """Если бота сделали админом, запускаем синхронизацию."""
    chat_id = event.chat.id
    if event.new_chat_member.is_chat_admin():
        logging.info(f"🔧 Бот стал админом в чате {chat_id}. Синхронизируем участников...")
        await save_all_chat_members(bot, chat_id)


@event_router.message(Command("sync_users"))
async def sync_users(message: types.Message, bot: Bot):
    """Команда для ручной синхронизации участников."""
    chat_id = message.chat.id
    logging.info(f"📋 Запрос синхронизации от {message.from_user.id} в чате {chat_id}")

    try:
        # Получаем список администраторов через безопасный запрос
        admins = await safe_telegram_request(lambda: bot.get_chat_administrators(chat_id))
        admin_ids = [admin.user.id for admin in admins]

        if message.from_user.id not in admin_ids:
            await safe_telegram_request(lambda: message.reply("🚫 Только администраторы могут синхронизировать."))
            return

        await save_all_chat_members(bot, chat_id)
        await safe_telegram_request(lambda: message.reply("✅ Синхронизация завершена."))
        logging.info(f"✅ Синхронизация чата {chat_id} завершена.")

    except Exception as e:
        logging.error(f"❌ Ошибка при синхронизации: {e}")
        await safe_telegram_request(lambda: message.reply(f"❌ Ошибка: {e}"))


@event_router.message()
async def track_all_messages(message: types.Message):
    """Сохраняет участников, отправляющих сообщения."""
    if message.from_user:  # Сохраняем всех, включая ботов
        await save_user_to_db(message.chat.id, message.from_user, left=False)


async def update_all_users(bot: Bot):
    """Обновляет участников во всех чатах из БД."""
    logging.info("📋 Запуск обновления всех чатов...")

    try:
        db = await db_instance.get_connection()
        async with db:
            async with db.execute("SELECT DISTINCT chat_id FROM chat_users") as cursor:
                chat_ids = await cursor.fetchall()

        for chat_id_tuple in chat_ids:
            chat_id = chat_id_tuple[0]
            logging.info(f"🔄 Синхронизация чата {chat_id}...")
            try:
                await save_all_chat_members(bot, chat_id)
                logging.info(f"✅ Чат {chat_id} обновлён.")
                await asyncio.sleep(1)  # Задержка между чатами для снижения нагрузки
            except Exception as e:
                logging.error(f"❌ Ошибка при обновлении чата {chat_id}: {e}")

    except Exception as e:
        logging.error(f"❌ Критическая ошибка в update_all_users: {e}")


__all__ = ["event_router", "update_all_users"]