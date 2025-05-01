import logging
import asyncio
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, ChatMemberOwner, ChatMemberAdministrator
from aiogram.filters import ChatMemberUpdatedFilter, IS_ADMIN
from aiogram.exceptions import TelegramAPIError
from dabase.database import db_instance
from handlers.satefy.user_utils import get_mention
from utils.telegram_queue import telegram_queue

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("aiohttp").setLevel(logging.WARNING)

event_router = Router()

async def determine_user_role(bot: Bot, chat_id: int, user_id: int) -> str:
    """Определяет роль пользователя в чате через Telegram API."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if isinstance(member, ChatMemberOwner):
            return 'owner'
        elif isinstance(member, ChatMemberAdministrator):
            return 'admin'
        elif member.status == 'restricted':
            return 'restricted'
        return 'member'
    except TelegramAPIError as e:
        logging.error(f"Ошибка при определении роли пользователя {user_id} в чате {chat_id}: {e}")
        return 'member'

async def user_exists_in_db(chat_id: int, user_id: int) -> tuple[bool, bool, str]:
    """Проверяет, есть ли пользователь в БД, и возвращает его текущий статус left и role."""
    conn = await db_instance.get_connection()
    try:
        async with conn.execute("SELECT left, role FROM chat_users WHERE chat_id = ? AND user_id = ?", 
                                (chat_id, user_id)) as cursor:
            result = await cursor.fetchone()
        if result:
            return True, result[0], result[1]
        return False, None, None
    except Exception as e:
        logging.error(f"Ошибка при проверке пользователя {user_id} в чате {chat_id}: {e}")
        return False, None, None
    finally:
        await conn.close()

async def save_user_to_db(bot: Bot, chat_id: int, user: types.User, left: bool, reason: str):
    """Сохраняет или обновляет пользователя в БД с указанием причины."""
    username = user.username.lower() if user.username else f"user_{user.id}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
    role = await determine_user_role(bot, chat_id, user.id)

    exists, current_left, current_role = await user_exists_in_db(chat_id, user.id)
    action = "добавлен" if not exists else "обновлён"
    needs_update = not exists or current_left != left or current_role != role or username != user.username or full_name != user.full_name

    logging.debug(f"Проверка {user.id} (@{username}) в БД (chat_id: {chat_id}, left: {left}, role: {role}, reason: {reason})")

    if not needs_update:
        logging.info(f"Пользователь {user.id} (@{username}) уже актуален в чате {chat_id}, причина: {reason}")
        return

    conn = await db_instance.get_connection()
    try:
        await conn.execute("""
            INSERT INTO chat_users (user_id, chat_id, username, full_name, left, role)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                left = excluded.left,
                role = excluded.role
        """, (user.id, chat_id, username, full_name, left, role))
        await conn.commit()
        logging.info(f"Пользователь {user.id} (@{username}) {action} в чате {chat_id} с ролью {role}, причина: {reason}")
        if username != (user.username.lower() if user.username else f"user_{user.id}"):
            logging.warning(f"⚠️ Username изменён для {user.id}: старый={user.username}, новый={username}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении пользователя {user.id} в чате {chat_id}: {e}")
    finally:
        await conn.close()

async def sync_chat_roles(bot: Bot, chat_id: int):
    """Синхронизирует роли всех пользователей чата с Telegram."""
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        admin_ids = set()
        
        for admin in chat_admins:
            role = 'owner' if isinstance(admin, ChatMemberOwner) else 'admin'
            await save_user_to_db(bot, chat_id, admin.user, left=False, reason="синхронизация ролей")
            admin_ids.add(admin.user.id)
            await asyncio.sleep(0.1)

        conn = await db_instance.get_connection()
        try:
            async with conn.execute("SELECT user_id, username, full_name FROM chat_users WHERE chat_id = ? AND left = 0", 
                                    (chat_id,)) as cursor:
                all_users = await cursor.fetchall()
            
            for row in all_users:
                user_id, username, full_name = row
                try:
                    member = await bot.get_chat_member(chat_id, user_id)
                    if member.status in ("member", "administrator", "creator", "restricted"):
                        user = types.User(id=user_id, is_bot=False, first_name=full_name.split()[0], 
                                        last_name=" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else None, 
                                        username=username)
                        role = 'owner' if member.status == "creator" else 'admin' if member.status == "administrator" else 'restricted' if member.status == "restricted" else 'member'
                        await save_user_to_db(bot, chat_id, user, left=False, reason="синхронизация ролей")
                    else:
                        user = types.User(id=user_id, is_bot=False, first_name=full_name.split()[0], 
                                        last_name=" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else None, 
                                        username=username)
                        await save_user_to_db(bot, chat_id, user, left=True, reason="синхронизация ролей: пользователь покинул чат")
                    await asyncio.sleep(0.1)
                except TelegramAPIError as e:
                    logging.error(f"Ошибка при проверке статуса пользователя {user_id} в чате {chat_id}: {e}")
            await conn.commit()
        finally:
            await conn.close()

        logging.info(f"Синхронизировано {len(chat_admins)} админов и {len(all_users)} участников в чате {chat_id}")
        return len(chat_admins)
    except TelegramAPIError as e:
        logging.error(f"Ошибка при синхронизации ролей в чате {chat_id}: {e}")
        return 0

@event_router.chat_member()
async def debug_chat_member(event: ChatMemberUpdated, bot: Bot):
    """Логирует все события ChatMemberUpdated для отладки."""
    try:
        chat_id = event.chat.id
        user = event.new_chat_member.user if event.new_chat_member else event.old_chat_member.user
        old_status = event.old_chat_member.status if event.old_chat_member else None
        new_status = event.new_chat_member.status if event.new_chat_member else None
        if old_status == "restricted" and new_status == "restricted":
            logging.debug(f"Игнорируем событие ChatMemberUpdated: пользователь {user.id} (@{user.username}) в чате {chat_id}, статус не изменился: restricted")
            return
        logging.info(f"Событие ChatMemberUpdated: пользователь {user.id} (@{user.username}) в чате {chat_id}, "
                     f"старый статус: {old_status}, новый статус: {new_status}")
        await save_user_to_db(bot, chat_id, user, left=new_status in ("left", "kicked"), 
                             reason=f"изменение статуса: {old_status} -> {new_status}")
    except Exception as e:
        logging.error(f"Ошибка в debug_chat_member для события {event}: {e}")

@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_ADMIN))
async def bot_became_admin(event: ChatMemberUpdated, bot: Bot):
    """Если бота сделали админом, синхронизирует роли."""
    chat_id = event.chat.id
    new_member = event.new_chat_member
    if new_member.user.id == bot.id and new_member.status in ("administrator", "creator"):
        logging.info(f"Бот стал админом в чате {chat_id}. Синхронизируем роли...")
        admin_count = await sync_chat_roles(bot, chat_id)
        try:
            await bot.send_message(chat_id, f"✅ Бот активирован! Сохранено {admin_count} администраторов.\n"
                                            "Роли участников синхронизированы.")
        except TelegramAPIError as e:
            logging.error(f"Ошибка отправки сообщения в чат {chat_id}: {e}")

@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=[("member", "administrator"), ("restricted", "administrator"), ("member", "creator"), ("restricted", "creator")]))
async def user_promoted_to_admin(event: ChatMemberUpdated, bot: Bot):
    """Обрабатывает назначение пользователя администратором."""
    user = event.new_chat_member.user
    chat_id = event.chat.id
    old_status = event.old_chat_member.status if event.old_chat_member else None
    logging.info(f"Пользователь {user.id} (@{user.username}) назначен администратором/владельцем в чате {chat_id} (старый статус: {old_status})")
    await save_user_to_db(bot, chat_id, user, left=False, reason=f"назначение администратором/владельцем (старый статус: {old_status})")

@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=("administrator", "member")))
async def user_demoted_from_admin(event: ChatMemberUpdated, bot: Bot):
    """Обрабатывает снятие пользователя с роли администратора."""
    user = event.old_chat_member.user
    chat_id = event.chat.id
    logging.info(f"Пользователь {user.id} (@{user.username}) снят с роли администратора в чате {chat_id}")
    await save_user_to_db(bot, chat_id, user, left=False, reason="снятие с роли администратора")

@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(None, "member")))
async def user_joined(event: ChatMemberUpdated, bot: Bot):
    """Сохраняет нового участника и отправляет приветствие."""
    user = event.new_chat_member.user
    chat_id = event.chat.id
    logging.info(f"Новый участник: {user.id} (@{user.username}) в чате {chat_id}")
    await save_user_to_db(bot, chat_id, user, left=False, reason="вход в чат")

    db = await db_instance.get_connection()
    try:
        async with db.execute(
            "SELECT welcome_text, welcome_media FROM chat_settings WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            result = await cursor.fetchone()
        if result and (result["welcome_text"] or result["welcome_media"]):
            mention = await get_mention(bot, chat_id, user.id)
            welcome_text = f"{mention}, {result['welcome_text']}" if result["welcome_text"] else mention
            welcome_media = result["welcome_media"]

            if welcome_media:
                if welcome_media.startswith("Ag"):
                    await telegram_queue.add_request(lambda: bot.send_animation(chat_id, welcome_media))
                elif welcome_media.startswith("BA"):
                    await telegram_queue.add_request(lambda: bot.send_photo(chat_id, welcome_media))
                elif welcome_media.startswith("Aw"):
                    await telegram_queue.add_request(lambda: bot.send_voice(chat_id, welcome_media))
                elif welcome_media.startswith("E"):
                    await telegram_queue.add_request(lambda: bot.send_video_note(chat_id, welcome_media))
                else:
                    await telegram_queue.add_request(lambda: bot.send_sticker(chat_id, welcome_media))
                if welcome_text and result["welcome_text"]:
                    await telegram_queue.add_request(lambda: bot.send_message(chat_id, welcome_text))
            else:
                await telegram_queue.add_request(lambda: bot.send_message(chat_id, welcome_text))
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке приветствия в чате {chat_id}: {e}")
    finally:
        await db.close()

@event_router.chat_member(ChatMemberUpdatedFilter(member_status_changed=("member", "left")))
async def user_left(event: ChatMemberUpdated, bot: Bot):
    """Обновляет статус ушедшего участника."""
    user = event.old_chat_member.user
    chat_id = event.chat.id
    logging.info(f"Участник покинул чат: {user.id} (@{user.username}) в чате {chat_id}")
    await save_user_to_db(bot, chat_id, user, left=True, reason="выход из чата")

@event_router.message(Command("sync_users"))
async def sync_users(message: types.Message, bot: Bot):
    """Команда для синхронизации ролей участников чата."""
    chat_id = message.chat.id
    logging.info(f"Синхронизация запрошена пользователем {message.from_user.id} в чате {chat_id}")

    try:
        admins = await bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in admins]

        if message.from_user.id not in admin_ids:
            await message.reply("🚫 Только администраторы могут использовать эту команду.")
            return

        admin_count = await sync_chat_roles(bot, chat_id)
        await message.reply(f"✅ Синхронизация завершена: сохранено {admin_count} администраторов и обновлены роли.")
    except TelegramAPIError as e:
        logging.error(f"Ошибка API: {e}")
        await message.reply(f"❌ Ошибка: {e}")

@event_router.message()
async def track_all_messages(message: types.Message, bot: Bot):
    """Сохраняет участников, отправляющих сообщения, и парсит системные сообщения о добавлении."""
    chat_id = message.chat.id

    if message.from_user:
        await save_user_to_db(bot, chat_id, message.from_user, left=False, reason="отправка сообщения")
        db = await db_instance.get_connection()
        try:
            await db.execute("INSERT OR IGNORE INTO messages (message_id, chat_id, user_id, timestamp) VALUES (?, ?, ?, ?)",
                             (message.message_id, chat_id, message.from_user.id, int(message.date.timestamp())))
            await db.commit()
            logging.debug(f"Сообщение {message.message_id} от {message.from_user.id} записано в чате {chat_id}")
        except Exception as e:
            logging.error(f"Ошибка при записи сообщения {message.message_id} в чате {chat_id}: {e}")
        finally:
            await db.close()

    if message.new_chat_members:
        for user in message.new_chat_members:
            if user.id != bot.id:
                logging.info(f"Новый участник добавлен админом: {user.id} (@{user.username}) в чате {chat_id}")
                await save_user_to_db(bot, chat_id, user, left=False, reason="добавлен админом")

async def update_all_users(bot: Bot):
    """Обновляет роли во всех чатах из базы данных."""
    logging.info("Запуск обновления всех чатов...")

    conn = await db_instance.get_connection()
    try:
        async with conn.execute("SELECT DISTINCT chat_id FROM chat_users") as cursor:
            chat_ids = await cursor.fetchall()

        for chat_id_tuple in chat_ids:
            chat_id = chat_id_tuple[0]
            logging.info(f"Синхронизация чата {chat_id}...")
            await sync_chat_roles(bot, chat_id)
            logging.info(f"Чат {chat_id} обновлён.")
    except Exception as e:
        logging.error(f"Ошибка в update_all_users: {e}")
    finally:
        await conn.close()

__all__ = ["event_router", "update_all_users"]