import sqlite3

def init_db():
    """
    Функция для создания и инициализации базы данных.
    """
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        registration_date TEXT,
        selected_universe TEXT DEFAULT NULL,  -- Выбранная вселенная
        is_blacklisted BOOLEAN DEFAULT 0,    -- Статус блокировки
        last_card_time TEXT DEFAULT NULL,    -- Время последнего получения карты
        total_points INTEGER DEFAULT 0,      -- Общая ценность всех карт
        spins INTEGER DEFAULT 0,             -- Количество доступных прокруток
        last_claimed TEXT DEFAULT NULL,      -- Время последнего получения бонуса
        daily_streak INTEGER DEFAULT 0       -- Количество дней подряд для ежедневного бонуса
    )
    """)

    # Таблица карт (универсальная, под вселенные)
    universes = ["marvel", "dc", "star_wars"]
    for universe in universes:
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS [{universe}] (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            photo_path TEXT,  -- Путь к изображению
            rarity TEXT,
            attack INTEGER,
            hp INTEGER,
            points INTEGER DEFAULT 0  -- Ценность карты
        )
        """)

    # Таблица карт пользователя
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_cards (
        user_id INTEGER,
        card_id INTEGER,
        universe TEXT,  -- Указание вселенной карты
        quantity INTEGER DEFAULT 1,  -- Количество карт
        PRIMARY KEY (user_id, card_id, universe),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)

    # Таблица промокодов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        promocode TEXT PRIMARY KEY,
        spins_bonus INTEGER,             -- Количество прокруток, которые добавляет промокод
        usage_limit INTEGER,             -- Максимальное количество использований
        usage_count INTEGER DEFAULT 0    -- Сколько раз промокод уже был использован
    )
    """)

    # Таблица использования промокодов пользователями
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_promocodes (
        user_id INTEGER,
        promocode TEXT,
        PRIMARY KEY (user_id, promocode),
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (promocode) REFERENCES promocodes (promocode)
    )
    """)

    # Таблица ассортимента магазина для пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_shop (
        user_id INTEGER,
        universe TEXT,
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT,
        item_value TEXT,
        price INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)

    conn.commit()
    conn.close()
    print("База данных успешно инициализирована.")
