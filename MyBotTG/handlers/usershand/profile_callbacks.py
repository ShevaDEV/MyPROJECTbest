import sqlite3
from aiogram import types, Router
from handlers.cardshand.cardsall import show_user_cards
from promo.promocode import handle_promocode_input
from aiogram.fsm.context import FSMContext
from handlers.usershand.change_universe import start_universe_change
from handlers.usershand.profil import show_profile

profile_callbacks_router = Router()

@profile_callbacks_router.callback_query(lambda c: c.data == "view_cards")
async def view_cards_from_profile(callback: types.CallbackQuery):
    """Обработчик кнопки 'Мои карты' в профиле."""
    await show_user_cards(callback.message)

@profile_callbacks_router.callback_query(lambda c: c.data == "use_promocode")
async def promocode_from_profile(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Промокод' в профиле."""
    await handle_promocode_input(callback, state)

@profile_callbacks_router.callback_query(lambda c: c.data == "change_universe")
async def process_change_universe(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Сменить вселенную'"""
    await callback.message.delete()  # Удаляем сообщение профиля
    await start_universe_change(callback, state)  # Запускаем смену вселенной

@profile_callbacks_router.callback_query(lambda c: c.data == "cancel_universe_selection")
async def cancel_universe_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает отмену выбора вселенной и возвращает профиль пользователя."""
    
    user_id = callback.from_user.id

    # Проверяем, есть ли профиль пользователя в БД
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()
    conn.close()

    await callback.message.delete()  # Удаляем сообщение с выбором вселенной
    await callback.answer("🔙 Возвращаюсь в профиль...")

    if user_exists:
        # Отправляем новый профиль пользователю
        await show_profile(callback.message.chat.id)
    else:
        await callback.message.answer("⚠️ Ошибка: профиль не найден. Попробуйте снова или зарегистрируйтесь с помощью /start.")

    await state.clear()  # Очищаем состояние FSM
