from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove
import sqlite3
from config import OWNER_ID

universecheck_router = Router()

# Состояния для управления вселенными
class ToggleUniverseStates(StatesGroup):
    waiting_for_universe_id = State()

def enable_universe(universe_id: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE universes SET enabled = 1 WHERE universe_id = ?", (universe_id,))
    conn.commit()
    conn.close()

def disable_universe(universe_id: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE universes SET enabled = 0 WHERE universe_id = ?", (universe_id,))
    conn.commit()
    conn.close()

def get_universe_status(universe_id: str) -> bool:
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT enabled FROM universes WHERE universe_id = ?", (universe_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

@universecheck_router.message(Command("toggle_universe"))
async def start_toggle_universe(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ У вас нет прав.")
        return

    await message.answer(
        "🔧 Введите ID вселенной (например, `marvel`):\n"
        "❌ Отмена: /cancel",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(ToggleUniverseStates.waiting_for_universe_id)

# Обработчик отмены ДО основного обработчика
@universecheck_router.message(Command("cancel"), ToggleUniverseStates.waiting_for_universe_id)
async def cancel_toggle_universe(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.")

@universecheck_router.message(ToggleUniverseStates.waiting_for_universe_id, F.text)
async def process_toggle_universe(message: types.Message, state: FSMContext):
    # Проверка на /cancel в тексте (если команда не сработала)
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Действие отменено.")
        return

    universe_id = message.text.strip().lower().replace(" ", "_")
    current_status = get_universe_status(universe_id)

    if current_status is None:
        await message.answer(f"❌ Вселенная с ID `{universe_id}` не найдена!")
        await state.clear()
        return

    new_status = not current_status
    if new_status:
        enable_universe(universe_id)
        status_text = "включена"
    else:
        disable_universe(universe_id)
        status_text = "отключена"

    await message.answer(f"✅ Вселенная `{universe_id}` {status_text}.")
    await state.clear()

@universecheck_router.message(Command("list_universes"))
async def list_universes_command(message: types.Message):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT universe_id, name, enabled FROM universes")
    universes = cursor.fetchall()
    conn.close()

    if not universes:
        await message.answer("📂 Список вселенных пуст.")
        return

    response = "🌌 Список вселенных:\n\n"
    for universe_id, name, enabled in universes:
        status = "✅ Включена" if enabled else "❌ Отключена"
        response += f"{status}\nID: `{universe_id}`\nНазвание: {name}\n\n"

    await message.answer(response, parse_mode="Markdown")