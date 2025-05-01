import logging
import asyncio
from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dabase.database import db_instance
from handlers.satefy.user_utils import is_admin_or_owner
from utils.telegram_queue import telegram_queue

welcome_router = Router()

# Константы для сообщений
ERROR_MESSAGE = "❌ Ошибка при выполнении команды."
NO_WELCOME_MESSAGE = "ℹ️ Приветствие не установлено. Используйте /setwelcome для настройки."
ADMIN_ONLY_MESSAGE = "🚫 Эта команда доступна только администраторам или владельцу."
ALREADY_SETTING_MESSAGE = "⚠️ Другой администратор уже устанавливает приветствие. Дождитесь завершения."
WELCOME_SET_MESSAGE = "✅ Приветствие установлено."
WELCOME_CLEARED_MESSAGE = "✅ Приветствие удалено. Новые участники больше не будут получать сообщения."
CANCELLED_MESSAGE = "🚫 Установка приветствия отменена."
INVALID_CONTENT_MESSAGE = "❌ Отправьте текст или медиа."
INVALID_MEDIA_MESSAGE = "❌ Отправьте медиа."
NO_CONTENT_MESSAGE = "❌ Ничего не установлено. Укажите хотя бы текст или медиа."

# Определяем состояния для FSM
class WelcomeForm(StatesGroup):
    waiting_for_content = State()
    waiting_for_media = State()

# Вспомогательная функция для безопасного удаления сообщений
async def delete_message_safe(bot: Bot, chat_id: int, message_id: int):
    try:
        chat = await bot.get_chat(chat_id)
        chat_member = await chat.get_member(bot.id)
        if chat_member.can_delete_messages:
            await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logging.error(f"❌ Ошибка при удалении сообщения {message_id} в чате {chat_id}: {e}")

# Вспомогательная функция для отправки медиа
async def send_media(bot: Bot, chat_id: int, media_id: str, welcome_text: str = None):
    try:
        if media_id.startswith("Ag"):
            await telegram_queue.add_request(lambda: bot.send_animation(chat_id, media_id))
        elif media_id.startswith("BA"):
            await telegram_queue.add_request(lambda: bot.send_photo(chat_id, media_id))
        elif media_id.startswith("Aw"):
            await telegram_queue.add_request(lambda: bot.send_voice(chat_id, media_id))
        elif media_id.startswith("E"):
            await telegram_queue.add_request(lambda: bot.send_video_note(chat_id, media_id))
        else:
            await telegram_queue.add_request(lambda: bot.send_sticker(chat_id, media_id))
        if welcome_text:
            await telegram_queue.add_request(lambda: bot.send_message(chat_id, welcome_text))
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке медиа в чат {chat_id}: {e}")
        await telegram_queue.add_request(lambda: bot.send_message(chat_id, ERROR_MESSAGE))

@welcome_router.message(Command("welcome"))
async def show_welcome(message: types.Message, bot: Bot, state: FSMContext):
    chat_id = message.chat.id

    db = await db_instance.get_connection()
    try:
        async with db.execute(
            "SELECT welcome_text, welcome_media FROM chat_settings WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            result = await cursor.fetchone()
        if not result or (not result["welcome_text"] and not result["welcome_media"]):
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, NO_WELCOME_MESSAGE)
            )
            return

        welcome_text = result["welcome_text"]
        welcome_media = result["welcome_media"]
        welcome_msg_id = None

        if welcome_media:
            await send_media(bot, chat_id, welcome_media, welcome_text)
            # Сохраняем ID последнего отправленного сообщения (примерно)
            welcome_msg_id = (await bot.send_message(chat_id, " ")).message_id
        elif welcome_text:
            sent_msg = await bot.send_message(chat_id, welcome_text)
            welcome_msg_id = sent_msg.message_id

        await state.update_data(welcome_msg_id=welcome_msg_id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Сменить", callback_data="set_welcome"),
                InlineKeyboardButton(text="Удалить", callback_data="clear_welcome")
            ]
        ])
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, "Что дальше?", reply_markup=keyboard)
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при показе приветствия для чата {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, ERROR_MESSAGE)
        )
    finally:
        await db.close()

@welcome_router.callback_query(lambda c: c.data in ["set_welcome", "clear_welcome", "cancel_welcome", "no_text", "done"])
async def process_welcome_callback(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    action = callback.data

    if action == "cancel_welcome":
        data = await state.get_data()
        if data.get("cancelled", False):
            await callback.answer("Ты уже отменил, хватит тыкать! 😛", show_alert=True)
            return
        await state.update_data(cancelled=True)
        await state.clear()
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, CANCELLED_MESSAGE)
        )
        first_msg_id = data.get("first_instruction_msg_id")
        if first_msg_id:
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, first_msg_id)
            )
        await telegram_queue.add_request(
            lambda: delete_message_safe(bot, chat_id, callback.message.message_id)
        )
        await callback.answer()
        return

    try:
        if not await is_admin_or_owner(bot, user_id, chat_id):
            await callback.answer("Эй, эта кнопка не для твоих шаловливых ручек! 😜", show_alert=True)
            return
    except Exception as e:
        logging.error(f"❌ Ошибка проверки админа для user_id {user_id} в чате {chat_id}: {e}")
        await callback.answer("❌ Ошибка проверки прав.", show_alert=True)
        return

    data = await state.get_data()
    welcome_msg_id = data.get("welcome_msg_id")

    if action == "set_welcome":
        current_state = await state.get_state()
        if current_state in [WelcomeForm.waiting_for_content.state, WelcomeForm.waiting_for_media.state]:
            await callback.message.answer(ALREADY_SETTING_MESSAGE)
        else:
            await state.update_data(admin_id=user_id, chat_id=chat_id, first_instruction_msg_id=None, instruction_msg_id=None)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Без текста", callback_data="no_text")],
                [InlineKeyboardButton(text="Отмена", callback_data="cancel_welcome")]
            ])
            msg = await callback.message.answer(
                "✍️ Отправьте текст приветствия или медиа (гиф, фото, голосовое, стикер, кружок).\nУ вас 30 секунд.",
                reply_markup=keyboard
            )
            await state.update_data(first_instruction_msg_id=msg.message_id)
            await state.set_state(WelcomeForm.waiting_for_content)
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, callback.message.message_id)
            )
            if welcome_msg_id:
                await telegram_queue.add_request(
                    lambda: delete_message_safe(bot, chat_id, welcome_msg_id)
                )
    elif action == "clear_welcome":
        db = await db_instance.get_connection()
        try:
            await db.execute(
                "UPDATE chat_settings SET welcome_text = NULL, welcome_media = NULL, last_updated = strftime('%s', 'now'), moderator_id = ? WHERE chat_id = ?",
                (user_id, chat_id)
            )
            await db.commit()
            logging.info(f"🗑 Приветствие для чата {chat_id} очищено модератором {user_id}")
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, WELCOME_CLEARED_MESSAGE)
            )
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, callback.message.message_id)
            )
            if welcome_msg_id:
                await telegram_queue.add_request(
                    lambda: delete_message_safe(bot, chat_id, welcome_msg_id)
                )
        except Exception as e:
            logging.error(f"❌ Ошибка при очистке приветствия для чата {chat_id}: {e}")
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, ERROR_MESSAGE)
            )
        finally:
            await db.close()
    elif action == "no_text":
        data = await state.get_data()
        first_msg_id = data.get("first_instruction_msg_id")
        if first_msg_id:
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, first_msg_id)
            )
        await state.update_data(welcome_text=None)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Готово", callback_data="done")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_welcome")]
        ])
        msg = await bot.send_message(
            chat_id,
            "✅ Текст не будет использован. Отправьте медиа (гиф, фото, голосовое, стикер, кружок).\nУ вас 30 секунд.",
            reply_markup=keyboard
        )
        await state.update_data(instruction_msg_id=msg.message_id)
        await state.set_state(WelcomeForm.waiting_for_media)
    elif action == "done":
        await save_welcome(chat_id, user_id, bot, state)

    await callback.answer()

@welcome_router.message(Command("setwelcome"))
async def start_setwelcome(message: types.Message, bot: Bot, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id

    current_state = await state.get_state()
    if current_state in [WelcomeForm.waiting_for_content.state, WelcomeForm.waiting_for_media.state]:
        await message.answer(ALREADY_SETTING_MESSAGE)
        return

    await state.update_data(admin_id=user_id, chat_id=chat_id, first_instruction_msg_id=None, instruction_msg_id=None)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без текста", callback_data="no_text")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_welcome")]
    ])
    msg = await message.answer(
        "✍️ Отправьте текст приветствия или медиа (гиф, фото, голосовое, стикер, кружок).\nУ вас 30 секунд.",
        reply_markup=keyboard
    )
    await state.update_data(first_instruction_msg_id=msg.message_id)
    await state.set_state(WelcomeForm.waiting_for_content)

@welcome_router.message(WelcomeForm.waiting_for_content)
async def process_welcome_content(message: types.Message, bot: Bot, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id

    data = await state.get_data()
    if not data or data.get("admin_id") != user_id or data.get("chat_id") != chat_id:
        return

    try:
        if not await is_admin_or_owner(bot, user_id, chat_id):
            await message.answer(ADMIN_ONLY_MESSAGE)
            await state.clear()
            return
    except Exception as e:
        logging.error(f"❌ Ошибка проверки админа для user_id {user_id} в чате {chat_id}: {e}")
        await message.answer(ERROR_MESSAGE)
        await state.clear()
        return

    welcome_text = None
    welcome_media = None

    if message.text:
        welcome_text = message.text
        await state.update_data(welcome_text=welcome_text)
        first_msg_id = data.get("first_instruction_msg_id")
        if first_msg_id:
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, first_msg_id)
            )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Готово", callback_data="done")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_welcome")]
        ])
        msg = await message.answer(
            "✅ Текст сохранён. Теперь отправьте медиа (по желанию).\nУ вас 30 секунд.",
            reply_markup=keyboard
        )
        await state.update_data(instruction_msg_id=msg.message_id)
        await state.set_state(WelcomeForm.waiting_for_media)
    elif message.animation:
        welcome_media = message.animation.file_id
    elif message.photo:
        welcome_media = message.photo[-1].file_id
    elif message.voice:
        welcome_media = message.voice.file_id
    elif message.sticker:
        welcome_media = message.sticker.file_id
    elif message.video_note:
        welcome_media = message.video_note.file_id

    if welcome_media:
        await state.update_data(welcome_media=welcome_media)
        await save_welcome(chat_id, user_id, bot, state)
    elif not welcome_text:
        await message.answer(INVALID_CONTENT_MESSAGE)

    await asyncio.sleep(30)
    if await state.get_state() == WelcomeForm.waiting_for_media.state:
        await save_welcome(chat_id, user_id, bot, state)

@welcome_router.message(WelcomeForm.waiting_for_media)
async def process_welcome_media(message: types.Message, bot: Bot, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id

    data = await state.get_data()
    if not data or data.get("admin_id") != user_id or data.get("chat_id") != chat_id:
        return

    try:
        if not await is_admin_or_owner(bot, user_id, chat_id):
            await message.answer(ADMIN_ONLY_MESSAGE)
            await state.clear()
            return
    except Exception as e:
        logging.error(f"❌ Ошибка проверки админа для user_id {user_id} в чате {chat_id}: {e}")
        await message.answer(ERROR_MESSAGE)
        await state.clear()
        return

    welcome_media = None
    if message.animation:
        welcome_media = message.animation.file_id
    elif message.photo:
        welcome_media = message.photo[-1].file_id
    elif message.voice:
        welcome_media = message.voice.file_id
    elif message.sticker:
        welcome_media = message.sticker.file_id
    elif message.video_note:
        welcome_media = message.video_note.file_id

    if welcome_media:
        await state.update_data(welcome_media=welcome_media)
        await save_welcome(chat_id, user_id, bot, state)
    else:
        await message.answer(INVALID_MEDIA_MESSAGE)

async def save_welcome(chat_id: int, user_id: int, bot: Bot, state: FSMContext):
    data = await state.get_data()
    welcome_text = data.get("welcome_text")
    welcome_media = data.get("welcome_media")
    first_instruction_msg_id = data.get("first_instruction_msg_id")
    instruction_msg_id = data.get("instruction_msg_id")

    if not welcome_text and not welcome_media:
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, NO_CONTENT_MESSAGE)
        )
        if first_instruction_msg_id:
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, first_instruction_msg_id)
            )
        if instruction_msg_id:
            await telegram_queue.add_request(
                lambda: delete_message_safe(bot, chat_id, instruction_msg_id)
            )
        await state.clear()
        return

    db = await db_instance.get_connection()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, welcome_text, welcome_media, last_updated, moderator_id) "
            "VALUES (?, ?, ?, strftime('%s', 'now'), ?)",
            (chat_id, welcome_text, welcome_media, user_id)
        )
        await db.commit()
        logging.info(f"👋 Приветствие для чата {chat_id} обновлено: текст='{welcome_text}', медиа={welcome_media}")

        if welcome_media:
            await send_media(bot, chat_id, welcome_media, welcome_text)
        else:
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, welcome_text)
            )
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, WELCOME_SET_MESSAGE)
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при сохранении приветствия в БД для чата {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, ERROR_MESSAGE)
        )
    finally:
        await state.clear()
        await db.close()

    if first_instruction_msg_id:
        await telegram_queue.add_request(
            lambda: delete_message_safe(bot, chat_id, first_instruction_msg_id)
        )
    if instruction_msg_id:
        await telegram_queue.add_request(
            lambda: delete_message_safe(bot, chat_id, instruction_msg_id)
        )

@welcome_router.message(Command("clearwelcome"))
async def clear_welcome(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id

    db = await db_instance.get_connection()
    try:
        await db.execute(
            "UPDATE chat_settings SET welcome_text = NULL, welcome_media = NULL, last_updated = strftime('%s', 'now'), moderator_id = ? WHERE chat_id = ?",
            (user_id, chat_id)
        )
        await db.commit()
        logging.info(f"🗑 Приветствие для чата {chat_id} очищено модератором {user_id}")
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, WELCOME_CLEARED_MESSAGE)
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при очистке приветствия для чата {chat_id}: {e}")
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, ERROR_MESSAGE)
        )
    finally:
        await db.close()