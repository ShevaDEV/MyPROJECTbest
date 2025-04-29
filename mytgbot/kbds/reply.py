import sqlite3
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_available_universes():
    """
    Получает список доступных вселенных из базы данных.
    """
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM universes WHERE enabled = 1")
    universes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return universes

def create_universe_selection_keyboard():
    """
    Создает клавиатуру для выбора вселенной.
    """
    universes = get_available_universes()
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(universe) for universe in universes],
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
