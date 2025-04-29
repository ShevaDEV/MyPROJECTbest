import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command
from handlers.satefy.user_utils import get_chat_members  # Импортируем функцию!

logging.basicConfig(level=logging.INFO)
list_router = Router()


@list_router.message(Command("list_users"))
async def cmd_list_users(message: types.Message, bot: Bot):
    """📋 Выводит список пользователей в чате."""
    chat_id = message.chat.id
    users = await get_chat_members(bot, chat_id)

    if isinstance(users, str):  # Если `get_chat_members` вернул ошибку как строку
        await message.reply(f"❌ Ошибка: {users}")
        return

    if not users:  # Если список пустой
        await message.reply("❌ В базе данных нет записей о пользователях этого чата.")
        return

    # 📋 **Сортируем пользователей по user_id**
    users.sort(key=lambda x: x[0])

    response = "📋 **Список пользователей в чате:**\n\n"
    for user_id, username in users:
        username_display = f"{username}" if username and username != "(без username)" else "(без username)"
        response += f"🆔 `{user_id}` | {username_display}\n"

    await message.reply(response)
