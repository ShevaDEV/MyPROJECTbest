import sqlite3
import random
from aiogram import Router, types, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_ID, CHANNEL_LINK

referal_router = Router()

# Функция проверки подписки
async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал."""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False  # Ошибка доступа к каналу

# Получение количества карт у пользователя
def get_user_card_count(user_id: int) -> int:
    """Подсчитывает количество карт у пользователя."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0] or 0
    conn.close()
    return count

# Проверка выполнения условий для реферала
async def check_referral_validity(user_id: int, bot: Bot):
    """
    Проверяет выполнение условий:
    - Приглашенный подписан на канал
    - Собрал 3 карты
    - Только после этого реферал засчитывается
    """
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT referrer_id, is_valid FROM referrals WHERE referral_id = ?", (user_id,))
    referral_data = cursor.fetchone()

    if not referral_data:
        conn.close()
        return

    referrer_id, is_valid = referral_data

    # Если уже засчитан — ничего не делаем
    if is_valid:
        conn.close()
        return  

    # Проверяем подписку
    if not await is_user_subscribed(bot, user_id):
        conn.close()
        return  # Если не подписан — не засчитываем

    # Проверяем, собрал ли 3 карты
    if get_user_card_count(user_id) < 3:
        conn.close()
        return  

    # Если все условия выполнены, засчитываем реферала
    cursor.execute("UPDATE referrals SET is_valid = 1 WHERE referral_id = ?", (user_id,))
    cursor.execute("UPDATE users SET spins = spins + 1 WHERE user_id = ?", (referrer_id,))  # 1 крутка пригласившему
    cursor.execute("UPDATE users SET spins = spins + 2 WHERE user_id = ?", (user_id,))  # 2 крутки приглашенному
    conn.commit()
    conn.close()

# Получение реферальной ссылки
def get_referral_link(user_id: int) -> str:
    """Возвращает реферальную ссылку пользователя."""
    return f"https://t.me/WhilacBot?start={user_id}"

# Создание клавиатуры
def referral_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для рефералов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Пригласить друзей", url=get_referral_link(user_id))],
        [InlineKeyboardButton(text="📊 Мои рефералы", callback_data="my_referrals")]
    ])

# Хендлер команды /referral
async def show_referral_info(message: types.Message):
    """Показывает реферальную информацию, заменяя профиль или отправляя новое сообщение."""
    user_id = message.chat.id
    referral_link = get_referral_link(user_id)

    text = (
        "🎯 *Приглашай друзей и получай бонусы!* 🎯\n\n"
        "📌 *Как получить награду?*\n"
        "1️⃣ Твой друг должен быть *новым игроком* (не использовал бота раньше)\n"
        f"2️⃣ Он должен *подписаться* на [наш канал]({CHANNEL_LINK})\n"
        "3️⃣ Также он должен *получить 3 карты* в игре\n\n"
        "🎁 *Что вы получите?*\n"
        "👤 *Ты* — 1 бесплатную крутку 🎡\n"
        "🆕 *Твой друг* — 2 бесплатные крутки 🎉\n"
        "🔥 *Бонус:* за каждые 5 приглашенных друзей ты получишь *ещё 2 крутки!*"
        "\n\n📢 *Приглашай друзей прямо сейчас!*"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Отправить другу", url=f"https://t.me/share/url?url={referral_link}")],
        [InlineKeyboardButton(text="Назад в профиль", callback_data="back_to_profile")]
    ])

    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except TelegramAPIError:
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")



# Хендлер "Мои рефералы"
@referal_router.callback_query(lambda c: c.data == "my_referrals")
async def my_referrals(callback: types.CallbackQuery):
    """Показывает список рефералов и бонусы."""
    user_id = callback.from_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND is_valid = 1", (user_id,))
    valid_referrals = cursor.fetchone()[0]

    extra_spins = (valid_referrals // 5) * 2  # +2 крутки за каждые 5 рефералов

    conn.close()

    await callback.message.edit_text(
        f"📊 *Ваши рефералы*\n\n"
        f"✅ Засчитано рефералов: *{valid_referrals}*\n"
        f"🎁 Бонусные крутки: *{valid_referrals}*\n"
        f"🔥 Доп. бонус за 5+ рефералов: *{extra_spins}*",
        parse_mode="Markdown"
    )
