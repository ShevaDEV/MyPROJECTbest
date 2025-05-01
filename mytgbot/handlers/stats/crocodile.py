import logging
import asyncio
import random
import time
from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dabase.database import db_instance
from handlers.satefy.user_utils import get_mention
from utils.telegram_queue import telegram_queue
import re

crocodile_router = Router()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("aiohttp").setLevel(logging.WARNING)

# Состояния для игры
class CrocodileGame(StatesGroup):
    waiting_for_explanation = State()
    waiting_for_guess = State()
    waiting_for_new_leader = State()

# Список слов для игры
WORDS = [
    "яблоко", "банан", "груша", "апельсин", "виноград", "киви", "манго", "ананас", "персик", "слива",
    "картошка", "морковь", "капуста", "помидор", "огурец", "лук", "чеснок", "брокколи", "тыква", "горох",
    "пицца", "суп", "борщ", "каша", "спагетти", "салат", "сэндвич", "бургер", "пельмени", "блины",
    "чай", "кофе", "сок", "вода", "молоко", "лимонад", "вино", "пиво", "квас", "компот",
    "хлеб", "сыр", "масло", "мясо", "рыба", "колбаса", "яйцо", "мёд", "варенье", "шоколад",
    "кот", "собака", "корова", "лошадь", "овца", "коза", "свинья", "курица", "утка", "гусь",
    "медведь", "волк", "лиса", "заяц", "олень", "тигр", "лев", "слон", "жираф", "обезьяна",
    "крокодил", "змея", "лягушка", "черепаха", "пингвин", "акула", "дельфин", "кит", "осьминог", "краб",
    "бабочка", "пчела", "муравей", "паук", "жук", "стрекоза", "кузнечик", "божья коровка", "червяк", "улитка",
    "попугай", "воробей", "голубь", "ворон", "сова", "орёл", "фламинго", "павлин", "лебедь", "кукушка",
    "мышь", "крыса", "хомяк", "белка", "ёж", "крот", "барсук", "выдра", "бобёр", "кенгуру",
    "панда", "коала", "носорог", "бегемот", "гепард", "леопард", "буйвол", "верблюд", "страус", "пеликан",
    "скорпион", "таракан", "муха", "комар", "оса", "шмель", "гусеница", "ёрш", "щука", "карась",
    "форель", "сом", "окунь", "тунец", "сельдь", "камбала", "скат", "мурена", "пиранья", "барракуда",
    "лемур", "сурикат", "мангуст", "енот", "опоссум", "дикобраз", "броненосец", "тушканчик", "варан", "игуана",
    "солнце", "луна", "звезда", "облако", "дождь", "снег", "ветер", "гроза", "туман", "радуга",
    "река", "море", "озеро", "водопад", "пруд", "ручей", "болото", "океан", "волна", "прилив",
    "песок", "камень", "глина", "земля", "трава", "лист", "цветок", "дерево", "куст", "пальма",
    "сосна", "берёза", "дуб", "клён", "ель", "кедр", "ива", "бамбук", "кактус", "мох",
    "гора", "холм", "долина", "пустыня", "лес", "степь", "тундра", "вулкан", "пещера", "ледник",
    "стул", "стол", "кровать", "диван", "шкаф", "полка", "зеркало", "лампа", "свеча", "часы",
    "телефон", "телевизор", "радио", "компьютер", "мышь", "клавиатура", "экран", "принтер", "сканер", "камера",
    "нож", "вилка", "ложка", "тарелка", "чашка", "кастрюля", "сковорода", "чайник", "микроволновка", "холодильник",
    "пылесос", "утюг", "фен", "щётка", "зубная паста", "мыло", "шампунь", "полотенце", "губка", "ведро",
    "молоток", "гвоздь", "отвёртка", "плоскогубцы", "пила", "дрель", "шуруп", "гаечный ключ", "лопата", "грабли",
    "карандаш", "ручка", "тетрадь", "линейка", "ножницы", "бумага", "клей", "ластик", "маркер", "книга",
    "рюкзак", "сумка", "кошелёк", "зонтик", "очки", "шляпа", "перчатки", "шарф", "ремень", "часы",
    "кольцо", "браслет", "серьги", "ожерелье", "ключ", "замок", "дверь", "окно", "крыша", "стена",
    "ковёр", "подушка", "одеяло", "простыня", "занавеска", "картина", "ваза", "цветочный горшок", "корзина", "ящик",
    "гитара", "пианино", "барабан", "труба", "скрипка", "флейта", "гармошка", "саксофон", "микрофон", "колонки",
    "машина", "автобус", "трамвай", "троллейбус", "поезд", "метро", "такси", "грузовик", "трактор", "мотоцикл",
    "велосипед", "самокат", "ролики", "скейтборд", "самолёт", "вертолёт", "дирижабль", "ракета", "спутник", "корабль",
    "лодка", "катер", "яхта", "паром", "подводная лодка", "каноэ", "байдарка", "плот", "сани", "карета",
    "бежать", "идти", "прыгать", "плавать", "летать", "ползать", "стоять", "сидеть", "лежать", "спать",
    "есть", "пить", "готовить", "резать", "жарить", "варить", "печь", "мыть", "чистить", "стирать",
    "читать", "писать", "рисовать", "петь", "танцевать", "играть", "смотреть", "слушать", "говорить", "кричать",
    "смеяться", "плакать", "улыбаться", "думать", "мечтать", "работать", "учиться", "учить", "строить", "ломать",
    "бросать", "ловить", "держать", "тянуть", "толкать", "нести", "поднимать", "опускать", "бить", "стрелять",
    "врач", "учитель", "полицейский", "пожарный", "водитель", "пилот", "моряк", "повар", "официант", "продавец",
    "инженер", "программист", "дизайнер", "художник", "музыкант", "актёр", "певец", "танцор", "писатель", "журналист",
    "строитель", "архитектор", "фермер", "садовник", "охотник", "рыбак", "тренер", "спортсмен", "учёный", "адвокат",
    "радость", "грусть", "злость", "страх", "удивление", "спокойствие", "счастье", "любовь", "ненависть", "скука",
    "усталость", "энергия", "волнение", "тревога", "уверенность", "сомнение", "гордость", "стыд", "восторг", "разочарование",
    "дружба", "одиночество", "мечта", "надежда", "паника", "удовольствие", "боль", "жара", "холод", "голод",
    "время", "день", "ночь", "утро", "вечер", "зима", "лето", "весна", "осень", "будущее",
    "прошлое", "правда", "ложь", "секрет", "тайна", "знание", "ум", "сила", "слабость", "свобода",
    "деньги", "работа", "игра", "жизнь", "смерть", "любовь", "война", "мир", "победа", "поражение",
    "мяч", "кукла", "робот", "пазл", "шахматы", "карты", "кубик", "конструктор", "футбол", "баскетбол",
    "теннис", "волейбол", "хоккей", "бокс", "карате", "йога", "фильм", "сериал", "театр", "цирк",
    "праздник", "подарок", "сюрприз", "костёр", "фонарь", "лук", "стрела", "ружьё", "палатка", "бинокль",
    "интернет", "смартфон", "планшет", "видео", "сообщение", "селфи", "фото", "приложение", "игра", "сайт",
    "наушники", "зарядка", "батарея", "экран", "кнопка", "клавиша", "кабель", "сигнал", "пароль", "дрон",
    "поцелуй", "объятие", "аплодисменты", "шёпот", "кивок", "жест", "рукопожатие", "подмигивание", "взгляд", "указатель",
    "хлопок", "шаг", "прыжок", "падение", "баланс", "вращение", "наклон", "рывок", "толчок", "захват",
    "карнавал", "фейерверк", "парад", "танцы", "маска", "костюм", "музыка", "традиция", "церемония", "украшение",
    "молния", "гравитация", "эхо", "тень", "радуга", "магнит", "огонь", "дым", "пар", "лёд",
    "звук", "свет", "цвет", "температура", "давление", "волна", "энергия", "атом", "планета", "космос",
    "плавание", "лыжи", "серфинг", "катание", "бой", "гимнастика", "бег", "прыжки", "метание", "гребля",
    "скорость", "тишина", "шум", "тепло", "холод", "запах", "вкус", "ощущение", "мысль", "воспоминание"
]

def escape_markdown(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2."""
    if not text:
        return ""
    return re.sub(r"([_*[\]()~`>#+-=|{}.!])", r"\\\1", text)

async def delete_message_safe(bot: Bot, chat_id: int, message_id: int):
    """Безопасно удаляет сообщение, проверяя права бота."""
    try:
        chat = await bot.get_chat(chat_id)
        chat_member = await chat.get_member(bot.id)
        if chat_member.can_delete_messages:
            await bot.delete_message(chat_id, message_id)
            logging.info(f"✅ Сообщение {message_id} успешно удалено из чата {chat_id}")
        else:
            logging.info(f"ℹ️ Бот не имеет прав удалять сообщения в чате {chat_id}")
    except Exception as e:
        if "message to delete not found" in str(e):
            logging.info(f"ℹ️ Сообщение {message_id} уже удалено из чата {chat_id}")
        else:
            logging.error(f"❌ Ошибка при удалении сообщения {message_id} в чате {chat_id}: {e}")

@crocodile_router.message(Command("crocodile"))
async def start_crocodile(message: types.Message, bot: Bot, state: FSMContext):
    """Запускает игру 'Крокодил'."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    current_state = await state.get_state()
    data = await state.get_data()
    start_time = data.get("start_time", 0)
    word = data.get("word", "")

    # Если игра идёт
    if current_state:
        elapsed_time = time.time() - start_time
        if elapsed_time < 300:  # До 5 минут
            await message.reply("⚠️ Игра уже идёт\\! Дождитесь 5 минут, чтобы начать новую, или продолжайте угадывать\\.", parse_mode="MarkdownV2")
            return
        else:  # После 5 минут
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, f"⏰ Старая игра завершена\\! Слово было: *{escape_markdown(word)}*\\. Начинаем новую\\!", parse_mode="MarkdownV2")
            )
            await state.clear()

    # Новая игра
    new_word = random.choice(WORDS)
    await state.update_data(leader_id=user_id, word=new_word, chat_id=chat_id, guesses=0, start_time=time.time())
    leader_mention = await get_mention(bot, chat_id, user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть слово", callback_data="show_word")],
        [InlineKeyboardButton(text="Сменить слово", callback_data="change_word")]
    ])
    await telegram_queue.add_request(
        lambda: bot.send_message(chat_id, f'🎉 Игра "Крокодил" началась\\! {leader_mention} объясняет слово\\.', reply_markup=keyboard, parse_mode="MarkdownV2")
    )
    await state.set_state(CrocodileGame.waiting_for_explanation)
    logging.info(f"Игра начата в чате {chat_id}, ведущий {user_id}, слово: {new_word}")

    # Запускаем таймеры
    await asyncio.create_task(check_game_timeout(chat_id, bot, state))

async def check_game_timeout(chat_id: int, bot: Bot, state: FSMContext):
    """Проверяет таймаут игры (5 и 10 минут)."""
    await asyncio.sleep(300)  # 5 минут
    if await state.get_state() in [CrocodileGame.waiting_for_explanation.state, CrocodileGame.waiting_for_guess.state]:
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, "⏰ Прошло 5 минут, никто не угадал\\! Можете начать новую игру с /crocodile\\.", parse_mode="MarkdownV2")
        )

    await asyncio.sleep(300)  # Ещё 5 минут (всего 10)
    if await state.get_state() is not None:
        data = await state.get_data()
        word = data.get("word")
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, f"⏰ Игра завершена \\(10 минут\\)\\. Слово было: *{escape_markdown(word)}*\\. Начни новую с /crocodile\\!", parse_mode="MarkdownV2")
        )
        await state.clear()

@crocodile_router.callback_query(lambda c: c.data in ["show_word", "change_word"])
async def process_leader_action(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """Обрабатывает действия ведущего: просмотр или смена слова."""
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await state.get_data()
    leader_id = data.get("leader_id")

    if user_id != leader_id:
        await callback.answer("Эй, эта кнопка только для ведущего! 😜", show_alert=True)
        return

    if callback.data == "show_word":
        word = data.get("word")
        await callback.answer(f"Твоё слово: {word}. Объясни его без использования этого слова!", show_alert=True)
    elif callback.data == "change_word":
        new_word = random.choice([w for w in WORDS if w != data.get("word")])
        await state.update_data(word=new_word)
        await callback.answer(f"Новое слово: {new_word}. Объясни его без использования этого слова!", show_alert=True)
        logging.info(f"Слово сменено в чате {chat_id}: {new_word}")

    await callback.answer()

@crocodile_router.message(CrocodileGame.waiting_for_explanation, lambda m: not m.text.startswith('/') if m.text else True)
async def process_explanation(message: types.Message, bot: Bot, state: FSMContext):
    """Обрабатывает объяснение ведущего. Пропускает команды."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    data = await state.get_data()

    if user_id != data.get("leader_id"):
        logging.info(f"Игнорируем сообщение от не-ведущего user_id {user_id} в чате {chat_id}")
        return  # Игнорируем сообщения не от ведущего

    word = data.get("word")
    if not message.text:  # Игнорируем нетекстовые сообщения
        logging.info(f"Игнорируем нетекстовое объяснение от user_id {user_id} в чате {chat_id}")
        return

    if word.lower() in message.text.lower():
        await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, "⚠️ Ведущий назвал слово\\! Игра окончена\\. Начни новую с /crocodile\\!", parse_mode="MarkdownV2")
        )
        await state.clear()
        logging.info(f"Игра завершена в чате {chat_id}: ведущий назвал слово {word}")
        return

    await telegram_queue.add_request(
        lambda: bot.send_message(chat_id, "▶️ Ведущий начал объяснять\\. Угадывайте\\!", parse_mode="MarkdownV2")
    )
    await state.set_state(CrocodileGame.waiting_for_guess)
    logging.info(f"Переход в waiting_for_guess для чата {chat_id}, слово: {word}, текущее состояние: {await state.get_state()}")

@crocodile_router.message(CrocodileGame.waiting_for_guess, lambda m: not m.text.startswith('/') if m.text else True)
async def process_guess(message: types.Message, bot: Bot, state: FSMContext):
    """Обрабатывает попытки угадывания слова. Пропускает команды."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    logging.info(f"Получено сообщение в waiting_for_guess: chat_id={chat_id}, user_id={user_id}, текст='{message.text}'")

    # Проверяем состояние
    current_state = await state.get_state()
    if current_state != CrocodileGame.waiting_for_guess.state:
        logging.warning(f"Неправильное состояние в чате {chat_id}: {current_state}")
        return

    # Получаем данные игры
    try:
        data = await state.get_data()
        word = data.get("word")
        leader_id = data.get("leader_id")
        start_time = data.get("start_time")
        logging.info(f"Данные игры в чате {chat_id}: word={word}, leader_id={leader_id}, start_time={start_time}")
    except Exception as e:
        logging.error(f"Ошибка при получении данных FSM в чате {chat_id}: {e}")
        return

    # Проверяем, что сообщение содержит текст
    if not message.text:
        logging.info(f"Игнорируем нетекстовое сообщение от user_id {user_id} в чате {chat_id}")
        return

    # Проверяем, не ведущий ли отправил сообщение
    if user_id == leader_id:
        if word.lower() in message.text.lower():
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, "⚠️ Ведущий назвал слово\\! Игра окончена\\. Начни новую с /crocodile\\!", parse_mode="MarkdownV2")
            )
            await state.clear()
            logging.info(f"Игра завершена в чате {chat_id}: ведущий назвал слово {word}")
        else:
            logging.info(f"Сообщение ведущего в чате {chat_id} игнорируется: '{message.text}'")
        return

    # Проверяем угадывание
    guess = message.text.strip().lower()
    logging.info(f"Попытка угадать в чате {chat_id}: '{guess}' против '{word}'")
    if word.lower() in guess:
        if time.time() - start_time > 600:  # 10 минут
            await telegram_queue.add_request(
                lambda: bot.send_message(chat_id, f"⏰ Слишком поздно\\! Слово было: *{escape_markdown(word)}*, но 10 минут уже прошло\\. Начни новую с /crocodile\\!", parse_mode="MarkdownV2")
            )
            await state.clear()
            logging.info(f"Игра завершена в чате {chat_id}: превышен таймаут")
            return

        # Угадал!
        logging.info(f"Слово угадано в чате {chat_id}: {word}")
        guesser_mention = await get_mention(bot, chat_id, user_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Стать ведущим", callback_data="become_leader")]
        ])
        msg = await telegram_queue.add_request(
            lambda: bot.send_message(chat_id, f"🎉 {guesser_mention} угадал слово: *{escape_markdown(word)}*\\! Нажми кнопку, чтобы стать ведущим\\.", 
                                    reply_markup=keyboard, parse_mode="MarkdownV2")
        )
        
        # Начисляем очки
        db = await db_instance.get_connection()
        try:
            await db.execute(
                "INSERT OR REPLACE INTO crocodile_scores (user_id, chat_id, score) "
                "VALUES (?, ?, COALESCE((SELECT score FROM crocodile_scores WHERE user_id = ? AND chat_id = ?)+2, 2))",
                (user_id, chat_id, user_id, chat_id)
            )
            await db.execute(
                "INSERT OR REPLACE INTO crocodile_scores (user_id, chat_id, score) "
                "VALUES (?, ?, COALESCE((SELECT score FROM crocodile_scores WHERE user_id = ? AND chat_id = ?)+1, 1))",
                (leader_id, chat_id, leader_id, chat_id)
            )
            await db.commit()
            logging.info(f"🎯 Очки начислены: {user_id} (+2) и {leader_id} (+1) в чате {chat_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка при начислении очков в чате {chat_id}: {e}")
        finally:
            await db.close()

        await state.update_data(guesser_id=user_id, guesser_msg_id=msg.message_id)
        await state.set_state(CrocodileGame.waiting_for_new_leader)
        logging.info(f"Переход в waiting_for_new_leader для чата {chat_id}")

        # Ждём 10 секунд, затем открываем кнопку для всех
        await asyncio.sleep(10)
        if await state.get_state() == CrocodileGame.waiting_for_new_leader.state:
            await telegram_queue.add_request(
                lambda: bot.edit_message_text(
                    chat_id=chat_id, 
                    message_id=msg.message_id, 
                    text=f"🎉 {guesser_mention} угадал слово: *{escape_markdown(word)}*\\! Любой может стать ведущим, нажимай кнопку\\!",
                    reply_markup=keyboard, parse_mode="MarkdownV2"
                )
            )
            logging.info(f"Кнопка 'Стать ведущим' открыта для всех в чате {chat_id}")

@crocodile_router.message(Command("stop_crocodile"))
async def stop_crocodile(message: types.Message, bot: Bot, state: FSMContext):
    """Завершает игру 'Крокодил'."""
    chat_id = message.chat.id
    data = await state.get_data()
    word = data.get("word", "неизвестно")
    await telegram_queue.add_request(
        lambda: bot.send_message(chat_id, f"🛑 Игра завершена\\! Слово было: *{escape_markdown(word)}*\\.", parse_mode="MarkdownV2")
    )
    await state.clear()
    logging.info(f"Игра остановлена в чате {chat_id}")

@crocodile_router.callback_query(lambda c: c.data == "become_leader")
async def become_leader(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """Обрабатывает выбор нового ведущего."""
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    data = await state.get_data()
    guesser_id = data.get("guesser_id")
    current_state = await state.get_state()

    if current_state != CrocodileGame.waiting_for_new_leader.state:
        await callback.answer("Игра уже идёт или завершена!", show_alert=True)
        return

    # Проверяем, прошло ли 10 секунд
    if time.time() - callback.message.date.timestamp() < 10:
        if user_id != guesser_id:
            await callback.answer("Эта кнопка пока только для угадавшего!", show_alert=True)
            return

    new_word = random.choice(WORDS)
    await state.update_data(leader_id=user_id, word=new_word, guesses=0, start_time=time.time())
    leader_mention = await get_mention(bot, chat_id, user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть слово", callback_data="show_word")],
        [InlineKeyboardButton(text="Сменить слово", callback_data="change_word")]
    ])
    await telegram_queue.add_request(
        lambda: bot.send_message(chat_id, f"🎉 {leader_mention} теперь ведущий\\! Объясняй слово\\.", reply_markup=keyboard, parse_mode="MarkdownV2")
    )
    await telegram_queue.add_request(
        lambda: delete_message_safe(bot, chat_id, callback.message.message_id)
    )
    await state.set_state(CrocodileGame.waiting_for_explanation)
    logging.info(f"Новый ведущий в чате {chat_id}: {user_id}, слово: {new_word}")
    await callback.answer()

    # Перезапускаем таймеры
    await asyncio.create_task(check_game_timeout(chat_id, bot, state))

@crocodile_router.message(Command("crocodile_top"))
async def show_local_leaderboard(message: types.Message, bot: Bot):
    """Показывает локальный топ игроков в чате."""
    chat_id = message.chat.id
    db = await db_instance.get_connection()
    try:
        async with db.execute(
            "SELECT user_id, score FROM crocodile_scores WHERE chat_id = ? ORDER BY score DESC LIMIT 10",
            (chat_id,)
        ) as cursor:
            leaders = await cursor.fetchall()
        if not leaders:
            await message.reply("🏆 В этом чате пока нет лидеров\\.", parse_mode="MarkdownV2")
            return

        leaderboard = "🏆 Топ игроков в этом чате:\n"
        for i, (user_id, score) in enumerate(leaders, 1):
            mention = await get_mention(bot, chat_id, user_id)
            leaderboard += f"{i}\\. {mention} — {score} очков\n"
        await message.reply(leaderboard, parse_mode="MarkdownV2")
    except Exception as e:
        logging.error(f"❌ Ошибка при показе локального лидерборда для чата {chat_id}: {e}")
        await message.reply("❌ Ошибка при показе лидерборда\\.", parse_mode="MarkdownV2")
    finally:
        await db.close()

@crocodile_router.message(Command("crocodile_global"))
async def show_global_leaderboard(message: types.Message, bot: Bot):
    """Показывает глобальный топ игроков."""
    chat_id = message.chat.id
    db = await db_instance.get_connection()
    try:
        async with db.execute(
            "SELECT user_id, SUM(score) as total_score FROM crocodile_scores GROUP BY user_id ORDER BY total_score DESC LIMIT 10"
        ) as cursor:
            leaders = await cursor.fetchall()
        if not leaders:
            await message.reply("🏆 Глобальных лидеров пока нет\\.", parse_mode="MarkdownV2")
            return

        leaderboard = "🏆 Глобальный топ игроков:\n"
        for i, (user_id, total_score) in enumerate(leaders, 1):
            mention = await get_mention(bot, chat_id, user_id)
            leaderboard += f"{i}\\. {mention} — {total_score} очков\n"
        await message.reply(leaderboard, parse_mode="MarkdownV2")
    except Exception as e:
        logging.error(f"❌ Ошибка при показе глобального лидерборда: {e}")
        await message.reply("❌ Ошибка при показе лидерборда\\.", parse_mode="MarkdownV2")
    finally:
        await db.close()