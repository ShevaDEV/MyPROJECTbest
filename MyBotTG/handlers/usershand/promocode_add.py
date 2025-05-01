from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import aiosqlite
from config import OWNER_ID

admin_router = Router()

# 📌 Состояния для работы с FSM
class AddPromocodeStates(StatesGroup):
    waiting_for_promocode = State()  # Ожидание промокода
    waiting_for_bonus_and_limit = State()  # Ожидание бонусов и лимита

# 🎛 Генерация клавиатуры с кнопкой отмены
def create_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

@admin_router.message(Command("add_promocode"))
@admin_router.message(F.text.lower() == "добавить промокод")
async def add_promocode_command(message: types.Message, state: FSMContext):
    """Начало добавления промокода"""
    if message.from_user.id != OWNER_ID:
        await message.answer("🚫 У вас нет прав на использование этой команды.")
        return

    await state.set_state(AddPromocodeStates.waiting_for_promocode)
    await message.answer(
        "📝 Введите *название промокода*:",
        reply_markup=create_cancel_keyboard(),
        parse_mode="Markdown"
    )

@admin_router.message(AddPromocodeStates.waiting_for_promocode)
async def process_promocode_name(message: types.Message, state: FSMContext):
    """Обрабатывает название промокода"""
    if message.text.lower() == "❌ отмена":
        await state.clear()
        await message.answer("🚫 Добавление промокода отменено.", reply_markup=ReplyKeyboardRemove())
        return

    await state.update_data(promocode=message.text)
    await state.set_state(AddPromocodeStates.waiting_for_bonus_and_limit)

    await message.answer(
        "🎰 Введите *количество бонусов* и *лимит* через пробел (например: `5 100`):",
        reply_markup=create_cancel_keyboard(),
        parse_mode="Markdown"
    )

@admin_router.message(AddPromocodeStates.waiting_for_bonus_and_limit)
async def process_bonus_and_limit(message: types.Message, state: FSMContext):
    """Обрабатывает количество бонусов и лимит"""
    if message.text.lower() == "❌ отмена":
        await state.clear()
        await message.answer("🚫 Добавление промокода отменено.", reply_markup=ReplyKeyboardRemove())
        return

    try:
        spins_bonus, usage_limit = map(int, message.text.split())
        if spins_bonus <= 0 or usage_limit <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите *два положительных числа* через пробел (например: `5 100`).")
        return

    data = await state.get_data()
    promocode = data["promocode"]

    # 🔹 Записываем в базу данных
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("""
            INSERT INTO promocodes (promocode, spins_bonus, usage_limit) 
            VALUES (?, ?, ?)
        """, (promocode, spins_bonus, usage_limit))
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ *Промокод* `{promocode}` *успешно добавлен!*\n"
        f"🎁 *Бонус:* `{spins_bonus}` прокруток\n"
        f"🔢 *Лимит:* `{usage_limit}` использований",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
