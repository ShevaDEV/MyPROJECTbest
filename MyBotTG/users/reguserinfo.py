import sqlite3
from datetime import datetime

# Регистрация пользователя
def register_user(user_id: int, username: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:  # Если пользователь не найден
        cursor.execute("""
        INSERT INTO users (user_id, username, registration_date, total_points)
        VALUES (?, ?, ?, 0)
        """, (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()

# Получение информации о пользователе
def get_user_info(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT user_id, username, registration_date, total_points FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    conn.close()

    if user:
        return {
            "user_id": user[0],
            "username": user[1],
            "registration_date": user[2],
            "total_points": user[3]  # Здесь индекс изменён на 3, если total_pts действительно четвёртое поле
        }
    return None
