from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove
import aiosqlite
from config import OWNER_ID

universecheck_router = Router()

# Состояния для управления вселенными
class ToggleUniverseStates(StatesGroup):
    waiting_for_universe_id = State()

async def enable_universe(universe_id: str):
    """🔹 Включает вселенную (делает enabled = 1)."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE universes SET enabled = 1 WHERE universe_id = ?", (universe_id,))
        await db.commit()

async def disable_universe(universe_id: str):
    """🔹 Отключает вселенную (делает enabled = 0)."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("UPDATE universes SET enabled = 0 WHERE universe_id = ?", (universe_id,))
        await db.commit()

async def get_universe_status(universe_id: str) -> bool:
    """🔹 Получает статус вселенной (включена или нет)."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT enabled FROM universes WHERE universe_id = ?", (universe_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

@universecheck_router.message(Command("toggle_universe"))
async def start_toggle_universe(message: types.Message, state: FSMContext):
    """Команда для переключения состояния вселенной."""
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

@universecheck_router.message(Command("cancel"), ToggleUniverseStates.waiting_for_universe_id)
async def cancel_toggle_universe(message: types.Message, state: FSMContext):
    """Отмена процесса переключения вселенной."""
    await state.clear()
    await message.answer("❌ Действие отменено.")

@universecheck_router.message(ToggleUniverseStates.waiting_for_universe_id, F.text)
async def process_toggle_universe(message: types.Message, state: FSMContext):
    """Переключает состояние вселенной (включает/отключает)."""
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Действие отменено.")
        return

    universe_id = message.text.strip().lower().replace(" ", "_")
    current_status = await get_universe_status(universe_id)

    if current_status is None:
        await message.answer(f"❌ Вселенная с ID `{universe_id}` не найдена!", parse_mode="Markdown")
        await state.clear()
        return

    new_status = not current_status
    if new_status:
        await enable_universe(universe_id)
        status_text = "включена ✅"
    else:
        await disable_universe(universe_id)
        status_text = "отключена ❌"

    await message.answer(f"✅ Вселенная `{universe_id}` {status_text}.", parse_mode="Markdown")
    await state.clear()

@universecheck_router.message(Command("list_universes"))
async def list_universes_command(message: types.Message):
    """Выводит список вселенных с их статусами."""
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT universe_id, name, enabled FROM universes") as cursor:
            universes = await cursor.fetchall()

    if not universes:
        await message.answer("📂 Список вселенных пуст.")
        return

    response = "🌌 **Список вселенных:**\n\n"
    for universe_id, name, enabled in universes:
        status = "✅ Включена" if enabled else "❌ Отключена"
        response += f"{status}\n**ID:** `{universe_id}`\n**Название:** {name}\n\n"

    await message.answer(response, parse_mode="Markdown")
