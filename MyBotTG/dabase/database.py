import aiosqlite

DB_PATH = "bot_database.db"

class Database:
    """Класс управления базой данных (Singleton)."""

    def __init__(self):
        """Инициализация объекта без открытия соединения."""
        self.ready = False  # Флаг готовности базы

    async def init_db(self):
        """Инициализация базы данных: создание таблиц."""
        if self.ready:  # Если БД уже инициализирована, повторно не выполняем
            print("✅ База данных уже инициализирована.")
            return

        print("🚀 Запуск инициализации базы данных...")

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row  # Упрощает доступ к данным через dict-like интерфейс
            print("📂 Подключение к БД установлено.")

            await db.executescript("""
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
            """)

            # 🔹 Добавляем начальные вселенные, если их нет
            print("🌌 Добавляем стандартные вселенные...")
            await db.executemany("""
                INSERT OR IGNORE INTO universes (universe_id, name, enabled)
                VALUES (?, ?, ?)
            """, [
                ("marvel", "Marvel", 1),
                ("star_wars", "Star Wars", 1),
            ])

            await db.commit()
        
        self.ready = True  # ✅ База данных готова!
        print("✅ База данных успешно инициализирована.")

    async def get_connection(self):
        """Всегда создаёт новое соединение с БД."""
        return await aiosqlite.connect(DB_PATH)

# ✅ Создаём единственный экземпляр БД
db_instance = Database()
