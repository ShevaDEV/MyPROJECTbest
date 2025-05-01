import logging
import asyncio
from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from dabase.database import db_instance
from utils.telegram_queue import telegram_queue

lock_router = Router()

# Разрешения для заблокированного чата
LOCKED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False
)

# Разрешения для разблокированного чата
UNLOCKED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False
)

# Константы для сообщений
ADMIN_ONLY_ERROR = "🚫 Эта команда доступна только администраторам или владельцу."
BOT_NO_PERMS_ERROR = "🚫 У бота недостаточно прав для управления чатом."
LOCK_ERROR = "❌ Ошибка при закрытии чата."
UNLOCK_ERROR = "❌ Ошибка при открытии чата."
LOCK_SUCCESS = "🔒 Чат закрыт. Писать могут только администраторы."
UNLOCK_SUCCESS = "🔓 Чат открыт. Все участники могут писать."
CALLBACK_ADMIN_ONLY_ERROR = "🚫 Только администраторы или владелец могут разблокировать чат."
CALLBACK_SUCCESS = "✅ Чат разблокирован!"

@lock_router.message(Command("lock"))
async def lock_chat(message: types.Message, bot: Bot):
    """🔒 Закрывает чат, ограничивая права участников."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    bot_member = await bot.get_chat_member(chat_id, bot.id)
    if not bot_member.can_restrict_members:
        await message.answer(BOT_NO_PERMS_ERROR)
        return

    try:
        await bot.set_chat_permissions(chat_id, LOCKED_PERMISSIONS)
        logging.info(f"🔒 Чат {chat_id} закрыт через API, модератор: {user_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка при закрытии чата {chat_id} через API: {e}")
        await message.answer(LOCK_ERROR)
        return

    db = await db_instance.get_connection()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, is_locked, last_updated, moderator_id) "
            "VALUES (?, 1, strftime('%s', 'now'), ?)",
            (chat_id, user_id)
        )
        await db.commit()
        logging.info(f"🔒 Статус чата {chat_id} обновлён в базе")
    except Exception as e:
        logging.error(f"❌ Ошибка при обновлении базы для чата {chat_id}: {e}")
    finally:
        await db.close()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"unlock_{chat_id}")]
    ])

    msg = await telegram_queue.add_request(
        lambda: bot.send_message(
            chat_id,
            LOCK_SUCCESS,
            reply_markup=keyboard
        )
    )

    await asyncio.sleep(5)
    await telegram_queue.add_request(
        lambda: bot.delete_message(chat_id, message.message_id)
    )

@lock_router.message(Command("unlock"))
async def unlock_chat(message: types.Message, bot: Bot):
    """🔓 Открывает чат, возвращая права участникам."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    await perform_unlock(chat_id, user_id, bot)

    await asyncio.sleep(5)
    await telegram_queue.add_request(
        lambda: bot.delete_message(chat_id, message.message_id)
    )

@lock_router.callback_query(lambda c: c.data.startswith("unlock_"))
async def process_unlock_callback(callback: types.CallbackQuery, bot: Bot):
    """Обрабатывает нажатие на кнопку разблокировки."""
    chat_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    await perform_unlock(chat_id, user_id, bot)

    # Удаляем сообщение с кнопкой и запись из базы
    message_id = callback.message.message_id
    await telegram_queue.add_request(
        lambda: bot.delete_message(chat_id, message_id)
    )
    db = await db_instance.get_connection()
    try:
        await db.execute(
            "DELETE FROM messages WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id)
        )
        await db.commit()
        logging.info(f"🗑 Запись сообщения {message_id} удалена из базы для чата {chat_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка при удалении записи сообщения {message_id} из базы: {e}")
    finally:
        await db.close()

    await callback.answer(CALLBACK_SUCCESS)

async def perform_unlock(chat_id: int, user_id: int, bot: Bot):
    """🔓 Выполняет разблокировку чата."""
    try:
        await bot.set_chat_permissions(chat_id, UNLOCKED_PERMISSIONS)
        logging.info(f"🔓 Чат {chat_id} открыт через API, модератор: {user_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка при открытии чата {chat_id} через API: {e}")
        await bot.send_message(chat_id, UNLOCK_ERROR)
        return

    db = await db_instance.get_connection()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, is_locked, last_updated, moderator_id) "
            "VALUES (?, 0, strftime('%s', 'now'), ?)",
            (chat_id, user_id)
        )
        await db.commit()
        logging.info(f"🔓 Статус чата {chat_id} обновлён в базе")
    except Exception as e:
        logging.error(f"❌ Ошибка при обновлении базы для чата {chat_id}: {e}")
    finally:
        await db.close()

    await telegram_queue.add_request(
        lambda: bot.send_message(chat_id, UNLOCK_SUCCESS)
    )