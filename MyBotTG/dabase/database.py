import sqlite3

def init_db():
    """
    Инициализация базы данных: создание таблиц.
    """
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        registration_date TEXT,
        selected_universe TEXT DEFAULT NULL,
        is_blacklisted BOOLEAN DEFAULT 0,
        last_card_time TEXT DEFAULT NULL,
        total_points INTEGER DEFAULT 0,
        spins INTEGER DEFAULT 0,
        last_claimed TEXT DEFAULT NULL,
        daily_streak INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE,  -- Уникальный код пользователя
        referred_by INTEGER DEFAULT NULL  -- Кто пригласил пользователя
    )
    """)

    # Таблица вселенных
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS universes (
        universe_id TEXT PRIMARY KEY,
        name TEXT,
        enabled BOOLEAN DEFAULT 0
    )
    """)

    # Таблица карт пользователя
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_cards (
        user_id INTEGER,
        card_id INTEGER,
        universe_id TEXT,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, card_id, universe_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (universe_id) REFERENCES universes (universe_id)
    )
    """)

    # Таблица промокодов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        promocode TEXT PRIMARY KEY,
        spins_bonus INTEGER,
        usage_limit INTEGER,
        usage_count INTEGER DEFAULT 0
    )
    """)

    # Таблица использования промокодов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_promocodes (
        user_id INTEGER,
        promocode TEXT,
        PRIMARY KEY (user_id, promocode),
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (promocode) REFERENCES promocodes (promocode)
    )
    """)

    # Таблица магазина
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_shop (
        user_id INTEGER,
        universe_id TEXT,
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT,
        item_value TEXT,
        price INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (universe_id) REFERENCES universes (universe_id)
    )
    """)

    # Таблица рефералов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
        referral_id INTEGER PRIMARY KEY,  -- ID приглашенного
        referrer_id INTEGER,  -- ID пригласившего
        joined_date TEXT,  -- Дата регистрации
        cards_collected INTEGER DEFAULT 0,  -- Карты, собранные рефералом
        is_valid BOOLEAN DEFAULT 0,  -- Засчитался ли реферал
        FOREIGN KEY (referral_id) REFERENCES users (user_id),
        FOREIGN KEY (referrer_id) REFERENCES users (user_id)
    )
    """)

    # Добавляем начальные вселенные, если их еще нет
    initial_universes = [
        ("marvel", "Marvel", 1),
        ("star_wars", "Star Wars", 1),
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO universes (universe_id, name, enabled)
    VALUES (?, ?, ?)
    """, initial_universes)

    conn.commit()
    conn.close()
    print("База данных успешно инициализирована.")
