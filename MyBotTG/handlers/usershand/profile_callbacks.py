from aiogram import types, Router
from handlers.cardshand.cardsall import show_user_cards
from promo.promocode import handle_promocode_input
from aiogram.fsm.context import FSMContext
from handlers.usershand.change_universe import start_universe_change

profile_callbacks_router = Router()

@profile_callbacks_router.callback_query(lambda c: c.data == "view_cards")
async def view_cards_from_profile(callback: types.CallbackQuery):
    """
    Обработчик кнопки 'Мои карты' в профиле.
    """
    # Вызываем существующую команду для показа карт
    await show_user_cards(callback.message)


@profile_callbacks_router.callback_query(lambda c: c.data == "use_promocode")
async def promocode_from_profile(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки 'Промокод' в профиле.
    """
    # Прямо вызываем обработчик ввода промокода
    await handle_promocode_input(callback, state)


@profile_callbacks_router.callback_query(lambda c: c.data == "change_universe")
async def process_change_universe(callback: types.CallbackQuery):
    """Обработчик кнопки 'Сменить вселенную'"""
    await start_universe_change(callback)