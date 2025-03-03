import aiosqlite
import random
from aiogram import Router, types, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_ID, CHANNEL_LINK
from dabase.database import db_instance  # Используем асинхронное подключение

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
async def get_user_card_count(user_id: int) -> int:
    """Подсчитывает количество карт у пользователя."""
    async with await db_instance.get_connection() as db:
        async with db.execute("SELECT COUNT(*) FROM user_cards WHERE user_id = ?", (user_id,)) as cursor:
            count = await cursor.fetchone()
    return count[0] if count else 0

# Проверка выполнения условий для реферала
async def check_referral_validity(user_id: int, bot: Bot):
    """
    Проверяет выполнение условий:
    - Приглашенный подписан на канал
    - Собрал 3 карты
    - Только после этого реферал засчитывается
    """
    async with await db_instance.get_connection() as db:
        async with db.execute("SELECT referrer_id, is_valid FROM referrals WHERE referral_id = ?", (user_id,)) as cursor:
            referral_data = await cursor.fetchone()

        if not referral_data:
            return

        referrer_id, is_valid = referral_data

        # Если уже засчитан — ничего не делаем
        if is_valid:
            return  

        # Проверяем подписку
        if not await is_user_subscribed(bot, user_id):
            return  # Если не подписан — не засчитываем

        # Проверяем, собрал ли 3 карты
        if await get_user_card_count(user_id) < 3:
            return  

        # Если все условия выполнены, засчитываем реферала
        await db.execute("UPDATE referrals SET is_valid = 1 WHERE referral_id = ?", (user_id,))
        await db.execute("UPDATE users SET spins = spins + 1 WHERE user_id = ?", (referrer_id,))  # 1 крутка пригласившему
        await db.execute("UPDATE users SET spins = spins + 2 WHERE user_id = ?", (user_id,))  # 2 крутки приглашенному
        await db.commit()

# Получение реферальной ссылки
def get_referral_link(user_id: int) -> str:
    """Возвращает реферальную ссылку пользователя."""
    return f"https://t.me/WhilacBot?start={user_id}"

# Создание клавиатуры
def referral_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для рефералов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Отправить другу", url=f"https://t.me/share/url?url={get_referral_link(user_id)}")],
        [InlineKeyboardButton(text="📊 Мои рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton(text="Назад в профиль", callback_data="back_to_profile")]
    ])

# Хендлер команды /referral
@referal_router.message(Command("referral"))
@referal_router.message(lambda message: message.text.lower() == "рефералы")
async def show_referral_info(message: types.Message):
    """Показывает реферальную информацию."""
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
        "🔥 *Бонус:* за каждые 5 приглашенных друзей ты получишь *ещё 2 крутки!*\n\n"
        f"📋 *Ваша реферальная ссылка:*\n`{referral_link}`\n\nПросто нажмите и скопируйте! ✨"
    )

    keyboard = referral_keyboard(user_id)

    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except TelegramAPIError:
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

# Хендлер "Мои рефералы"
@referal_router.callback_query(lambda c: c.data == "my_referrals")
async def my_referrals(callback: types.CallbackQuery):
    """Показывает список рефералов и бонусы."""
    user_id = callback.from_user.id

    async with await db_instance.get_connection() as db:
        async with db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND is_valid = 1", (user_id,)) as cursor:
            valid_referrals = await cursor.fetchone()

    valid_referrals = valid_referrals[0] if valid_referrals else 0
    extra_spins = (valid_referrals // 5) * 2  # +2 крутки за каждые 5 рефералов

    await callback.message.edit_text(
        f"📊 *Ваши рефералы*\n\n"
        f"✅ Засчитано рефералов: *{valid_referrals}*\n"
        f"🎁 Бонусные крутки: *{valid_referrals}*\n"    
        f"🔥 Доп. бонус за 5+ рефералов: *{extra_spins}*",
        parse_mode="Markdown"
    )
