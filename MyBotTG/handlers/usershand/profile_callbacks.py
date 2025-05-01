from aiogram import types, Router
from handlers.cardshand.cardsall import show_user_cards
from promo.promocode import handle_promocode_input
from aiogram.fsm.context import FSMContext
from handlers.usershand.change_universe import start_universe_change
from handlers.usershand.profil import show_profile
from handlers.usershand.referal import show_referral_info

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
    """Отмена выбора вселенной и возвращаем в профиль пользователя."""
    await callback.message.delete()  
    await callback.answer("🔙 Возвращаюсь в профиль...")

    await show_profile(callback)  # Отправляем профиль пользователя
    await state.clear()  # Очищаем состояние FSM

@profile_callbacks_router.callback_query(lambda c: c.data == "view_referrals")
async def view_referrals_from_profile(callback: types.CallbackQuery):
    """Обработчик кнопки 'Рефералы' в профиле."""
    await callback.message.delete()  # Удаляем сообщение профиля
    await show_referral_info(callback.message)  # Показываем реферальную систему

@profile_callbacks_router.callback_query(lambda c: c.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    """Обработчик кнопки 'Назад в профиль'."""
    await callback.message.delete()  # Удаляем реферальное сообщение
    await show_profile(callback)  # Передаем callback.message в show_profile
