import sqlite3

def fetch_cards_by_rarity(universe: str) -> dict:
    """
    Возвращает количество карт в базе данных по редкостям для выбранной вселенной.
    :param universe: Название вселенной.
    :return: Словарь, где ключ - редкость, значение - количество карт.
    """
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        SELECT rarity, COUNT(card_id)
        FROM [{universe}]
        GROUP BY rarity
        """)
        return {row[0]: row[1] for row in cursor.fetchall()}
