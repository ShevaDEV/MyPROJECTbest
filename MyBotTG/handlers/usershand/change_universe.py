import sqlite3
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

change_universe_router = Router()

# Определяем состояния ФСМ
class ChangeUniverseState(StatesGroup):
    waiting_for_universe = State()
    waiting_for_confirmation = State()  # Добавляем этап подтверждения

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
    
    conn.commit()
    conn.close()

async def start_universe_change(callback: types.CallbackQuery, state: FSMContext):
    """Запуск смены вселенной через ФСМ."""
    user_id = callback.from_user.id

    available_universes = get_available_universes()
    if not available_universes:
        await callback.message.answer("❌ Нет доступных вселенных для выбора.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"change_universe_{uid}")]
            for name, uid in available_universes.items()
        ] + [
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_universe_selection")]
        ]
    )

    await callback.message.answer(
        "🌌 Выберите новую вселенную (⚠️ Ваши текущие карты будут удалены! Очки останутся):",
        reply_markup=keyboard
    )
    await callback.answer()
    await state.set_state(ChangeUniverseState.waiting_for_universe)



@change_universe_router.callback_query(F.data.startswith("change_universe_"))
async def process_universe_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор новой вселенной (запрашивает подтверждение)."""
    user_id = callback.from_user.id
    new_universe_id = callback.data.split("_", 2)[2]  # Теперь берём ID правильно

    # Сохраняем выбранную вселенную во временное состояние
    await state.update_data(new_universe=new_universe_id)

    # Клавиатура подтверждения
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_universe_change")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_universe_change")]
        ]
    )

    await callback.message.answer(
        "⚠️ **Внимание!**\n\nПри смене вселенной **все ваши карты будут удалены**.\n"
        "Ваши очки останутся нетронутыми.\n\nВы уверены, что хотите сменить вселенную?",
        reply_markup=confirm_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()
    await state.set_state(ChangeUniverseState.waiting_for_confirmation)  # Ожидаем подтверждения

@change_universe_router.callback_query(F.data == "confirm_universe_change")
async def confirm_change_universe(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает смену вселенной и выполняет очистку карт."""
    user_id = callback.from_user.id

    # Получаем новую вселенную из состояния
    data = await state.get_data()
    new_universe_id = data.get("new_universe")

    if not new_universe_id:
        await callback.message.answer("⚠️ Ошибка: новая вселенная не найдена. Попробуйте снова.")
        return

    await reset_user_universe(user_id)

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET selected_universe = ? WHERE user_id = ?", (new_universe_id, user_id))
    conn.commit()
    conn.close()

    await callback.message.answer("🎉 Вы успешно сменили вселенную! Ваши карты были удалены.")
    await callback.answer()
    await state.clear()

@change_universe_router.callback_query(F.data == "cancel_universe_change")
async def cancel_change_universe(callback: types.CallbackQuery, state: FSMContext):
    """Отмена смены вселенной."""
    await callback.message.answer("Отмена смены вселенной. Ваши карты сохранены.")
    await callback.answer()
    await state.clear()
