from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import OWNER_ID

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """
    Генерация главной клавиатуры для пользователя.
    """
    # Основные кнопки
    keyboard = [
        [KeyboardButton(text="Дай карту"), KeyboardButton(text="Мои карты")],
        [KeyboardButton(text="Профиль"), KeyboardButton(text="Магазин")],
        [KeyboardButton(text="Лидеры")]
    ]

    # Добавляем кнопки администратора, если пользователь является владельцем
    if user_id == OWNER_ID:
        keyboard.append([KeyboardButton(text="Добавить карту")])
        keyboard.append([KeyboardButton(text="Обновить магазин"), KeyboardButton(text="Добавить промокод")])
        keyboard.append([KeyboardButton(text="Карты в базе")])  # Новая кнопка

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
