from aiogram import Router, types
from aiogram.filters import Command
from config import OWNER_ID
import sqlite3

admin_universe_router = Router()

@admin_universe_router.message(Command("toggle_universe"))
async def toggle_universe(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, is_enabled FROM universes")
        universes = cursor.fetchall()

    if not universes:
        await message.answer("В базе данных нет вселенных.")
        return

    keyboard = types.InlineKeyboardMarkup()
    for name, is_enabled in universes:
        status = "✅ Включена" if is_enabled else "❌ Отключена"
        keyboard.add(
            types.InlineKeyboardButton(
                text=f"{name.capitalize()} - {status}",
                callback_data=f"toggle:{name}:{1 if is_enabled == 0 else 0}"
            )
        )

    await message.answer("Выберите вселенную для изменения состояния:", reply_markup=keyboard)

@admin_universe_router.callback_query(lambda c: c.data.startswith("toggle"))
async def toggle_universe_callback(callback: types.CallbackQuery):
    _, universe, new_state = callback.data.split(":")
    new_state = int(new_state)

    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE universes SET is_enabled = ? WHERE name = ?
        """, (new_state, universe))
        conn.commit()

    status = "включена" if new_state else "отключена"
    await callback.message.edit_text(f"Вселенной '{universe.capitalize()}' теперь {status}.")
    await callback.answer("Статус вселенной обновлен.")
