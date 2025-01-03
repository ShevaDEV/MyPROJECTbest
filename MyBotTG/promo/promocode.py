from aiogram import Router, types, F
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from asyncio import sleep
import sqlite3

promocode_router = Router()

class PromoCodeState(StatesGroup):
    """Состояния для ввода промокода."""
    waiting_for_promocode = State()

class PromoCodeCallback(CallbackData, prefix="promocode"):
    """Коллбек для инлайн-кнопки 'Ввести промокод'."""
    action: str

def promocode_keyboard() -> types.InlineKeyboardMarkup:
    """Создаёт клавиатуру с кнопкой 'Ввести промокод'."""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🎁 Ввести промокод",
                    callback_data=PromoCodeCallback(action="enter").pack()
                )
            ]
        ]
    )

@promocode_router.callback_query(PromoCodeCallback.filter(F.action == "enter"))
async def handle_promocode_input(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Ввести промокод'."""
    await callback.message.edit_text("Введите ваш промокод в сообщении. У вас есть 30 секунд!")
    await state.set_state(PromoCodeState.waiting_for_promocode)

    # Устанавливаем таймер на 30 секунд
    async def timer():
        await sleep(30)
        current_state = await state.get_state()
        if current_state == PromoCodeState.waiting_for_promocode:
            await callback.message.answer("⏳ Время для ввода промокода истекло. Попробуйте ещё раз.")
            await state.clear()

    # Запускаем таймер асинхронно
    callback.bot.create_task(timer())

@promocode_router.message(PromoCodeState.waiting_for_promocode)
async def process_promocode(message: types.Message, state: FSMContext):
    """Обрабатывает ввод промокода."""
    promocode = message.text.strip()
    user_id = message.from_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Проверяем существование промокода
    cursor.execute("""
        SELECT promocode, spins_bonus, usage_limit, usage_count
        FROM promocodes
        WHERE promocode = ?
    """, (promocode,))
    promocode_data = cursor.fetchone()

    if not promocode_data:
        # Если промокод неверный, отправляем сообщение, но не сбрасываем состояние
        await message.answer("❌ Неверный промокод! Попробуйте ещё раз.")
        conn.close()
        return

    promocode, spins_bonus, usage_limit, usage_count = promocode_data

    if usage_count >= usage_limit:
        await message.answer("❌ Этот промокод уже исчерпан.")
        await state.clear()
        conn.close()
        return

    cursor.execute("""
        SELECT 1
        FROM user_promocodes
        WHERE user_id = ? AND promocode = ?
    """, (user_id, promocode))
    if cursor.fetchone():
        await message.answer("❌ Вы уже использовали этот промокод!")
        await state.clear()
        conn.close()
        return

    # Если проверки пройдены, начисляем бонусы
    cursor.execute("UPDATE users SET spins = spins + ? WHERE user_id = ?", (spins_bonus, user_id))
    cursor.execute("INSERT INTO user_promocodes (user_id, promocode) VALUES (?, ?)", (user_id, promocode))
    cursor.execute("UPDATE promocodes SET usage_count = usage_count + 1 WHERE promocode = ?", (promocode,))
    conn.commit()
    conn.close()

    # Успешное использование промокода
    await message.answer(f"🎉 Промокод {promocode} успешно активирован! Вы получили {spins_bonus} прокруток.")
    await state.clear()
