import aiosqlite
import logging

DB_PATH = "bot_database.db"

logging.basicConfig(level=logging.INFO)


class Database:
    """Класс управления базой данных (Singleton)."""

    def __init__(self):
        """Инициализация объекта без открытия соединения."""
        self.ready = False  # Флаг готовности базы

    async def init_db(self):
        """Инициализация базы данных: создание таблиц."""
        if self.ready:
            logging.info("✅ База данных уже инициализирована.")
            return

        logging.info("🚀 Запуск инициализации базы данных...")

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row  # Доступ к данным через dict-like интерфейс
            logging.info("📂 Подключение к БД установлено.")

            # Создаём таблицы
            await db.executescript("""
            PRAGMA foreign_keys = ON;

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
                referral_code TEXT UNIQUE,
                referred_by INTEGER DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS universes (
                universe_id TEXT PRIMARY KEY,
                name TEXT,
                enabled BOOLEAN DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS user_cards (
                user_id INTEGER,
                card_id INTEGER,
                universe_id TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, card_id, universe_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (universe_id) REFERENCES universes (universe_id)
            );

            CREATE TABLE IF NOT EXISTS user_shop (
                user_id INTEGER,
                universe_id TEXT,
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT,
                item_value TEXT,
                price INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (universe_id) REFERENCES universes (universe_id)
            );

            CREATE TABLE IF NOT EXISTS promocodes (
                promocode TEXT PRIMARY KEY,
                spins_bonus INTEGER,
                usage_limit INTEGER,
                usage_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS referrals (
                referral_id INTEGER PRIMARY KEY,
                referrer_id INTEGER,
                joined_date TEXT,
                cards_collected INTEGER DEFAULT 0,
                is_valid BOOLEAN DEFAULT 0,
                FOREIGN KEY (referral_id) REFERENCES users (user_id),
                FOREIGN KEY (referrer_id) REFERENCES users (user_id)
            );

            CREATE TABLE IF NOT EXISTS moderation (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                chat_id INTEGER, 
                user_id INTEGER, 
                username TEXT DEFAULT NULL,
                mute_until INTEGER DEFAULT 0,
                ban_until INTEGER DEFAULT 0,  
                ban_status BOOLEAN DEFAULT 0,
                reason TEXT, 
                moderator_id INTEGER, 
                timestamp INTEGER DEFAULT (strftime('%s', 'now'))
            );

            CREATE TABLE IF NOT EXISTS warns_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                moderator_id INTEGER,
                timestamp INTEGER,
                expire_at INTEGER,
                FOREIGN KEY (chat_id, user_id) REFERENCES moderation (chat_id, user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_users (
                user_id INTEGER,
                chat_id INTEGER,
                username TEXT,
                full_name TEXT,
                left BOOLEAN DEFAULT 0,
                role TEXT DEFAULT 'member',
                PRIMARY KEY (user_id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER,
                chat_id INTEGER,
                user_id INTEGER,
                timestamp INTEGER,
                PRIMARY KEY (message_id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                purge_period INTEGER DEFAULT 86400,  -- 24 часа по умолчанию в секундах
                rules TEXT DEFAULT NULL,
                is_locked INTEGER DEFAULT 0,  -- ✅ 0 = открыт, 1 = закрыт
                welcome_text TEXT DEFAULT NULL,
                welcome_media TEXT DEFAULT NULL,
                last_updated INTEGER DEFAULT (strftime('%s', 'now')),
                moderator_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS crocodile_scores (
                user_id INTEGER,
                chat_id INTEGER,
                score INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            );
            """)

            # Добавляем индексы для оптимизации запросов
            await db.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_moderation ON moderation(chat_id, user_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_warns ON warns_log(chat_id, user_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_chat_users_chat_id ON chat_users(chat_id);
            CREATE INDEX IF NOT EXISTS idx_chat_users_user_id ON chat_users(user_id);
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id_timestamp ON messages(chat_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_chat_rules_chat_id ON chat_settings(chat_id);
            CREATE INDEX IF NOT EXISTS idx_crocodile_scores_user_id_chat_id ON crocodile_scores(user_id, chat_id);
            """)

            # Добавляем начальные вселенные, если их нет
            logging.info("🌌 Добавляем стандартные вселенные...")
            await db.executemany("""
                INSERT OR IGNORE INTO universes (universe_id, name, enabled)
                VALUES (?, ?, ?)
            """, [
                ("marvel", "Marvel", 1),
                ("star_wars", "Star Wars", 1),
            ])

            await db.commit()

        self.ready = True
        logging.info("✅ База данных успешно инициализирована.")

    async def get_connection(self):
        """Создаёт новое соединение с БД."""
        conn = await aiosqlite.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = aiosqlite.Row
        return conn


# Создаём единственный экземпляр БД
db_instance = Database()