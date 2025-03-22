import aiosqlite
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

change_universe_router = Router()

# Определяем состояния ФСМ
class ChangeUniverseState(StatesGroup):
    waiting_for_universe = State()
    waiting_for_confirmation = State()  # Этап подтверждения


async def get_available_universes():
    """Получает список доступных вселенных из базы данных."""
    async with aiosqlite.connect("bot_database.db") as conn:
        cursor = await conn.execute("SELECT universe_id, name FROM universes WHERE enabled = 1")
        universes = await cursor.fetchall()
        return {name: universe_id for universe_id, name in universes}


async def reset_user_universe(user_id: int):
    """Удаляет все карты пользователя, но сохраняет очки."""
    async with aiosqlite.connect("bot_database.db") as conn:
        await conn.execute("DELETE FROM user_cards WHERE user_id = ?", (user_id,))
        await conn.commit()


async def start_universe_change(callback: types.CallbackQuery, state: FSMContext):
    """Запуск смены вселенной через ФСМ."""
    available_universes = await get_available_universes()
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
    try:
        new_universe_id = callback.data.split("_", 1)[1]
    except IndexError:
        await callback.message.answer("⚠️ Ошибка: невозможно определить выбранную вселенную.")
        return

    # Проверяем, существует ли вселенная
    async with aiosqlite.connect("bot_database.db") as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM universes WHERE universe_id = ?", (new_universe_id,))
        exists = await cursor.fetchone()
    
    if not exists or exists[0] == 0:
        await callback.message.answer("❌ Ошибка: выбранная вселенная не существует!")
        return

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

    async with aiosqlite.connect("bot_database.db") as conn:
        await conn.execute("UPDATE users SET selected_universe = ? WHERE user_id = ?", (new_universe_id, user_id))
        await conn.commit()

    await callback.message.answer("🎉 Вы успешно сменили вселенную! Ваши карты были удалены.")
    await callback.answer()
    await state.clear()


@change_universe_router.callback_query(F.data == "cancel_universe_change")
async def cancel_change_universe(callback: types.CallbackQuery, state: FSMContext):
    """Отмена смены вселенной."""
    await callback.message.answer("Отмена смены вселенной. Ваши карты сохранены.")
    await callback.answer()
    await state.clear()
