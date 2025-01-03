from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import OWNER_ID
import sqlite3

admin_router = Router()

# Состояния для работы с FSM
class AddPromocodeStates(StatesGroup):
    waiting_for_promocode = State()  # Ожидание ввода промокода
    waiting_for_bonus_and_limit = State()  # Ожидание ввода количества бонусов и лимита

# Генерация клавиатуры с кнопкой отмены
def create_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру с кнопкой отмены."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

@admin_router.message(Command("addpromocode"))
@admin_router.message(F.text.lower() == "добавить промокод")
async def add_promocode_command(message: types.Message, state: FSMContext):
    """
    Начало команды добавления промокода.
    """
    # Проверяем права доступа
    if message.from_user.id != OWNER_ID:
        await message.answer("У вас нет прав на использование этой команды.")
        return

    # Переходим в состояние ожидания промокода
    await state.set_state(AddPromocodeStates.waiting_for_promocode)
    await message.answer(
        "Введите название промокода:",
        reply_markup=create_cancel_keyboard()
    )

@admin_router.message(AddPromocodeStates.waiting_for_promocode)
async def process_promocode_name(message: types.Message, state: FSMContext):
    """
    Обработка названия промокода.
    """
    if message.text.lower() == "отмена":
        await message.answer("Добавление промокода отменено.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    # Сохраняем название промокода во временное хранилище FSM
    await state.update_data(promocode=message.text.strip())

    # Переходим в состояние ожидания бонусов и лимита
    await state.set_state(AddPromocodeStates.waiting_for_bonus_and_limit)
    await message.answer(
        "Введите количество бонусов и лимит использования через пробел (например: 5 100):",
        reply_markup=create_cancel_keyboard()
    )

@admin_router.message(AddPromocodeStates.waiting_for_bonus_and_limit)
async def process_bonus_and_limit(message: types.Message, state: FSMContext):
    """
    Обработка количества бонусов и лимита использования.
    """
    if message.text.lower() == "отмена":
        await message.answer("Добавление промокода отменено.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    # Извлекаем данные из сообщения
    input_text = message.text.strip().split()
    if len(input_text) != 2:
        await message.answer("Неверный формат. Введите два числа через пробел (например: 5 100).")
        return

    try:
        spins_bonus, usage_limit = map(int, input_text)
    except ValueError:
        await message.answer("Количество бонусов и лимит должны быть числами.")
        return

    if spins_bonus <= 0 or usage_limit <= 0:
        await message.answer("Количество бонусов и лимит должны быть положительными числами.")
        return

    # Извлекаем промокод из состояния
    data = await state.get_data()
    promocode = data["promocode"]

    # Сохраняем промокод в базу данных
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO promocodes (promocode, spins_bonus, usage_limit) 
        VALUES (?, ?, ?)
    """, (promocode, spins_bonus, usage_limit))
    conn.commit()
    conn.close()

    # Завершаем состояние
    await state.clear()
    await message.answer(
        f"Промокод {promocode} успешно добавлен!\n"
        f"Бонусы: {spins_bonus} прокруток\n"
        f"Лимит: {usage_limit} использований.",
        reply_markup=ReplyKeyboardRemove()
    )
