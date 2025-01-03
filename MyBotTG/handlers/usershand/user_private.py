from aiogram import types, Router, F
from aiogram.filters import CommandStart
from handlers.cardshand.cardsall import show_user_cards
from users.reguserinfo import register_user, get_user_info
from kbds.admin_reply import get_main_keyboard

router = Router()

@router.message(F.chat.type == 'private', CommandStart())
async def start_cmd(message: types.Message):
    # Регистрируем пользователя
    register_user(message.from_user.id, message.from_user.username)

    # Проверяем, зарегистрирован ли пользователь
    user_info = get_user_info(message.from_user.id)
    if user_info:
        # Генерация клавиатуры
        keyboard = get_main_keyboard(user_id=message.from_user.id)

        # Если регистрация прошла успешно, отправляем сообщение с клавиатурой
        await message.answer(
            f"Добро пожаловать, {user_info['username']}!\n"
            f"Дата вашей регистрации: {user_info['registration_date']}",
            reply_markup=keyboard  # Клавиатура для пользователя
        )
    else:
        # Если регистрация не удалась, отправляем сообщение об ошибке
        await message.answer("Произошла ошибка с регистрацией.")
