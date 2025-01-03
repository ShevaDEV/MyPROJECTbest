from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import AVAILABLE_UNIVERSES

def create_universe_selection_keyboard():
    """
    Создает клавиатуру для выбора вселенной.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(universe.capitalize()) for universe in AVAILABLE_UNIVERSES],
        ],
        resize_keyboard=True
    )

def create_main_menu_keyboard():
    """
    Создает основное меню после выбора вселенной.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Дай карту"), KeyboardButton(text="Мои карты")],
            [KeyboardButton(text="Профиль"), KeyboardButton(text="Магазин")],
            [KeyboardButton(text="Лидеры")]
        ],
        resize_keyboard=True
    )
