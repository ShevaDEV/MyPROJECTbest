from aiogram.filters.callback_data import CallbackData


class RarityCallback(CallbackData, prefix="rarity"):
    universe: str  # Вселенная, например, "marvel"
    rarity_type: str  # Редкость карт


class OwnerRarityCallback(CallbackData, prefix="owner_rarity"):
    universe: str
    rarity_type: str



class PaginationCallback(CallbackData, prefix="paginate"):
    rarity_type: str
    index: int

class AdminPaginationCallback(CallbackData, prefix="admin_paginate"):
    rarity_type: str
    index: int



class ReturnCallback(CallbackData, prefix="return"):
    action: str


class EditCardCallback(CallbackData, prefix="edit_card"):
    action: str  # edit_rarity, edit_points, delete
    card_id: int
    universe: str
