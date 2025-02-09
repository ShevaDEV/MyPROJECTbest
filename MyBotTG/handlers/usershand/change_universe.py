import sqlite3
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

change_universe_router = Router()

# Определяем состояния ФСМ
class ChangeUniverseState(StatesGroup):
    waiting_for_universe = State()

def get_available_universes():
    """Получает список доступных вселенных из базы данных."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT universe_id, name FROM universes WHERE enabled = 1")
    universes = cursor.fetchall()
    conn.close()
    return {name: universe_id for universe_id, name in universes}

async def reset_user_universe(user_id: int):
    """Удаляет все карты пользователя, но сохраняет очки."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Удаляем карты пользователя
    cursor.execute("DELETE FROM user_cards WHERE user_id = ?", (user_id,))
    cursor.execute("UPDATE users SET selected_universe = NULL WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()

async def start_universe_change(callback: types.CallbackQuery):
    """Запуск смены вселенной через ФСМ."""
    user_id = callback.from_user.id

    available_universes = get_available_universes()
    if not available_universes:
        await callback.message.answer("❌ Нет доступных вселенных для выбора.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"universe_{uid}")] for name, uid in available_universes.items()]
    )

    await callback.message.answer("🌌 Выберите новую вселенную:", reply_markup=keyboard)
    await callback.answer()  # Закрываем всплывающее уведомление
    await callback.bot.get_fsm().set_state(user_id, ChangeUniverseState.waiting_for_universe)

@change_universe_router.callback_query(F.data.startswith("universe_"))
async def process_universe_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор новой вселенной."""
    user_id = callback.from_user.id
    new_universe_id = callback.data.split("_")[1]

    await reset_user_universe(user_id)

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET selected_universe = ? WHERE user_id = ?", (new_universe_id, user_id))
    conn.commit()
    conn.close()

    await callback.message.answer(f"🎉 Вы успешно сменили вселенную на новую!")
    await callback.answer()
    await state.clear()
