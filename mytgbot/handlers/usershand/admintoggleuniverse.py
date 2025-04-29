from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite
from config import OWNER_ID

admin_universe_router = Router()

@admin_universe_router.message(Command("toggle_universe"))
async def toggle_universe(message: types.Message):
    """Выбор вселенной для включения/выключения"""
    if message.from_user.id != OWNER_ID:
        await message.answer("🚫 У вас нет прав на использование этой команды.")
        return

    # 🔹 Получаем список вселенных
    async with aiosqlite.connect("bot_database.db") as db:
        cursor = await db.execute("SELECT name, enabled FROM universes")
        universes = await cursor.fetchall()

    if not universes:
        await message.answer("📂 В базе данных нет вселенных.")
        return

    # 🎛 Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{name.capitalize()} - {'✅ Включена' if enabled else '❌ Отключена'}",
            callback_data=f"toggle:{name}:{1 if enabled == 0 else 0}"
        )]
        for name, enabled in universes
    ])

    await message.answer("🔧 Выберите вселенную для изменения состояния:", reply_markup=keyboard)

@admin_universe_router.callback_query(lambda c: c.data.startswith("toggle"))
async def toggle_universe_callback(callback: types.CallbackQuery):
    """Обрабатывает переключение состояния вселенной"""
    _, universe, new_state = callback.data.split(":")
    new_state = int(new_state)

    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE universes SET enabled = ? WHERE name = ?", (new_state, universe))
        await db.commit()

    status = "✅ включена" if new_state else "❌ отключена"
    await callback.message.edit_text(f"🌌 *Вселенная* `{universe.capitalize()}` *теперь {status}*.", parse_mode="Markdown")
    await callback.answer("Статус вселенной обновлен.")
