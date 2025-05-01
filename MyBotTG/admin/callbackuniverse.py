from aiogram.filters.callback_data import CallbackData

class UniverseCallback(CallbackData, prefix="view"):
    universe: str  # Название вселенной, например, "marvel"
