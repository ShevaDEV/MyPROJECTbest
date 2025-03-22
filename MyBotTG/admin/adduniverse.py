from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardRemove
import aiosqlite
from config import OWNER_ID

adduniverse_router = Router()

# Состояния для добавления вселенной
class AddUniverseStates(StatesGroup):
    waiting_for_universe_name = State()

async def add_universe(universe_id: str, name: str) -> bool:
    """Асинхронное добавление вселенной в базу данных."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("PRAGMA foreign_keys = ON")  # Включаем поддержку внешних ключей
        
        # Проверяем, существует ли уже такая вселенная
        async with db.execute("SELECT universe_id FROM universes WHERE universe_id = ?", (universe_id,)) as cursor:
            if await cursor.fetchone():
                return False  # Вселенная уже существует
        
        # Добавляем вселенную
        await db.execute(
            "INSERT INTO universes (universe_id, name, enabled) VALUES (?, ?, ?)",
            (universe_id, name, 0)
        )

        # Создаём таблицу для карт этой вселенной
        await db.execute(f"""
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

        await db.commit()
        return True

@adduniverse_router.message(Command("add_universe"))
async def start_add_universe(message: types.Message, state: FSMContext):
    """Запуск процесса добавления вселенной."""
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ У вас нет прав.")
        return

    await message.answer(
        "📝 Введите название вселенной (например, DC Comics):\n"
        "❌ Отмена: /cancel",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddUniverseStates.waiting_for_universe_name)

@adduniverse_router.message(Command("cancel"), AddUniverseStates.waiting_for_universe_name)
async def cancel_add_universe(message: types.Message, state: FSMContext):
    """Отмена процесса добавления вселенной."""
    await state.clear()
    await message.answer("❌ Добавление отменено.")

@adduniverse_router.message(AddUniverseStates.waiting_for_universe_name, F.text)
async def process_universe_name(message: types.Message, state: FSMContext):
    """Обрабатывает введённое название вселенной и добавляет её в базу данных."""
    # Проверяем, не ввёл ли пользователь команду /cancel вручную
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Добавление отменено.")
        return

    universe_name = message.text.strip()
    universe_id = universe_name.lower().replace(" ", "_")

    if await add_universe(universe_id, universe_name):
        await message.answer(f"✅ Вселенная «{universe_name}» добавлена!\nID: `{universe_id}`", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Вселенная «{universe_name}» уже существует!")

    await state.clear()
