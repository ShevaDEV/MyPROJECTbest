from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove
import sqlite3
from config import OWNER_ID

adduniverse_router = Router()

# Состояния для добавления вселенной
class AddUniverseStates(StatesGroup):
    waiting_for_universe_name = State()

def add_universe(universe_id: str, name: str) -> bool:
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    
    # Проверка существования вселенной
    cursor.execute("SELECT universe_id FROM universes WHERE universe_id = ?", (universe_id,))
    if cursor.fetchone():
        conn.close()
        return False

    # Добавление вселенной
    cursor.execute(
        "INSERT INTO universes (universe_id, name, enabled) VALUES (?, ?, ?)",
        (universe_id, name, 0)
    )
    
    # Создание таблицы для карт
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS [{universe_id}] (
        card_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        photo_path TEXT,
        rarity TEXT,
        attack INTEGER,
        hp INTEGER,
        points INTEGER DEFAULT 0
    )
    """)
    
    conn.commit()
    conn.close()
    return True

@adduniverse_router.message(Command("add_universe"))
async def start_add_universe(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ У вас нет прав.")
        return

    await message.answer(
        "📝 Введите название вселенной (например, DC Comics):\n"
        "❌ Отмена: /cancel",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddUniverseStates.waiting_for_universe_name)

# Обработчик отмены ДО основного обработчика
@adduniverse_router.message(Command("cancel"), AddUniverseStates.waiting_for_universe_name)
async def cancel_add_universe(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Добавление отменено.")

@adduniverse_router.message(AddUniverseStates.waiting_for_universe_name, F.text)
async def process_universe_name(message: types.Message, state: FSMContext):
    # Проверка на /cancel в тексте (если команда не сработала)
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено.")
        return

    universe_name = message.text.strip()
    universe_id = universe_name.lower().replace(" ", "_")

    if add_universe(universe_id, universe_name):
        await message.answer(f"✅ Вселенная «{universe_name}» добавлена!\nID: `{universe_id}`", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Вселенная «{universe_name}» уже существует!")

    await state.clear()