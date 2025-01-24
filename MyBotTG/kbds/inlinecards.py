from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from handlers.cardshand.callbackcards import RarityCallback, OwnerRarityCallback, PaginationCallback, AdminPaginationCallback, ReturnCallback, EditCardCallback


def rarity_keyboard_for_user(user_cards: dict, total_cards: dict, universe: str) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с кнопками редкостей для пользователей.
    :param user_cards: Словарь с количеством карт у пользователя по редкостям.
    :param total_cards: Словарь с общим количеством карт в базе по редкостям.
    :param universe: Вселенная карт.
    :return: InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()
    rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]

    for rarity in rarities:
        user_count = user_cards.get(rarity, 0)
        total_count = total_cards.get(rarity, 0)

        builder.row(
            InlineKeyboardButton(
                text=f"{rarity.capitalize()} ({user_count} из {total_count})",
                callback_data=RarityCallback(universe=universe, rarity_type=rarity).pack()
            )
        )

    return builder.as_markup()


def rarity_keyboard_for_owner(universe: str) -> InlineKeyboardMarkup:
    from dabase.databasehelp import fetch_cards_by_rarity

    total_cards = fetch_cards_by_rarity(universe)
    builder = InlineKeyboardBuilder()
    rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]

    for rarity in rarities:
        total_count = total_cards.get(rarity, 0)
        builder.row(
            InlineKeyboardButton(
                text=f"{rarity.capitalize()} ({total_count})",
                callback_data=OwnerRarityCallback(universe=universe, rarity_type=rarity).pack()
            )
        )

    return builder.as_markup()



def pagination_keyboard(rarity, index, total, include_return=True) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для пагинации.
    :param rarity: Текущая редкость карт.
    :param index: Индекс текущей карты.
    :param total: Общее количество карт.
    :param include_return: Флаг для добавления кнопки "Вернуться".
    :return: InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    if total > 1:
        builder.row(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=PaginationCallback(rarity_type=rarity, index=(index - 1) % total).pack()
            ),
            InlineKeyboardButton(
                text=f"{index + 1}/{total}",
                callback_data="noop"  # Неприменяемая кнопка, отображающая текущий счётчик
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=PaginationCallback(rarity_type=rarity, index=(index + 1) % total).pack()
            )
        )

    if include_return:
        builder.row(
            InlineKeyboardButton(
                text="Вернуться",
                callback_data=ReturnCallback(action="to_categories").pack()
            )
        )

    return builder.as_markup()


def admin_pagination_keyboard(rarity, index, total) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для пагинации карт владельца.
    :param rarity: Текущая редкость карт.
    :param index: Индекс текущей карты.
    :param total: Общее количество карт.
    :return: InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    if total > 1:
        builder.row(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AdminPaginationCallback(rarity_type=rarity, index=(index - 1) % total).pack()
            ),
            InlineKeyboardButton(
                text=f"{index + 1}/{total}",
                callback_data="noop"  # Неприменяемая кнопка, отображающая текущий счётчик
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=AdminPaginationCallback(rarity_type=rarity, index=(index + 1) % total).pack()
            )
        )

    return builder.as_markup()



def edit_card_keyboard(card_id, universe) -> InlineKeyboardMarkup:
    """
    Создает инлайн-кнопки для редактирования карты.
    :param card_id: ID карты.
    :param universe: Вселенная карты.
    :return: InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✏️ Редкость",
            callback_data=EditCardCallback(action="edit_rarity", card_id=card_id, universe=universe).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Очки",
            callback_data=EditCardCallback(action="edit_points", card_id=card_id, universe=universe).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Карту",
            callback_data=EditCardCallback(action="delete", card_id=card_id, universe=universe).pack()
        )
    )

    return builder.as_markup()
