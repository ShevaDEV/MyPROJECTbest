from aiogram import types, Router, F
from aiogram.filters import CommandStart, Command
from handlers.cardshand.cardsall import show_user_cards
from users.reguserinfo import register_user, get_user_info
from kbds.admin_reply import get_main_keyboard
from config import OWNER_ID  # ID администратора

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

@router.message(F.chat.type == 'private', Command("help"))
async def help_cmd(message: types.Message):
    """
    Обрабатывает команду /help и отправляет список доступных команд.
    """
    # Общие команды
    help_text = (
        "ℹ️ *Доступные команды:*\n\n"
        "👤 *Общие команды:*\n"
        "\\/start \\- Начать или перезапустить взаимодействие с ботом\n"
        "\\/card \\- Получить карту\n"
        "\\/daily \\- Получить ежедневный бонус\n"
        "\\/cards \\- Просмотреть свои карты\n"
        "\\/profile \\- Просмотреть свой профиль\n"
        "\\/shop \\- Магазин\n\n"
        "🎮 *Дополнительные команды:*\n"
        "\\/select\\_universe \\- Выбрать вселенную\n"
    )

    # Добавляем админские команды, если пользователь — администратор
    if message.from_user.id == OWNER_ID:
        help_text += (
            "\n🛠️ *Админские команды:*\n"
            "\\/addcard \\- Добавить новую карту\n"
            "\\/add\\_promocode \\- Просмотреть карты в базе\n"
            "\\/view\\_cards \\- Просмотреть карты в базе\n"
            "\\/list\\_universes \\- Все вселенные\n"
            "\\/toggle\\_universe \\- Включить либо выключить вселенную\n"
            "\\/add\\_universe \\- Добавить вселенную\n"
            "\\/update\\_shop \\- Обновить магазин\n"
        )

    await message.answer(help_text, parse_mode="MarkdownV2")
