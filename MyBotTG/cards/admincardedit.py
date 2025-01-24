import os
import sqlite3
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from handlers.cardshand.callbackcards import EditCardCallback
import random

admincardedit_router = Router()

# Диапазоны для атаки и здоровья по редкости
RARITY_RANGES = {
    "обычная": {"attack": (10, 30), "hp": (20, 50)},
    "редкая": {"attack": (30, 50), "hp": (50, 80)},
    "эпическая": {"attack": (50, 80), "hp": (80, 120)},
    "легендарная": {"attack": (80, 120), "hp": (120, 180)},
    "мифическая": {"attack": (120, 180), "hp": (180, 250)},
}

class EditPointsState(StatesGroup):
    waiting_for_points = State()

@admincardedit_router.callback_query(EditCardCallback.filter(F.action == "edit_rarity"))
async def edit_rarity(callback: types.CallbackQuery, callback_data: EditCardCallback):
    card_id = callback_data.card_id
    universe = callback_data.universe

    # Создаем клавиатуру для выбора новой редкости
    builder = InlineKeyboardBuilder()
    rarities = ["обычная", "редкая", "эпическая", "легендарная", "мифическая"]
    for rarity in rarities:
        builder.row(
            InlineKeyboardButton(
                text=rarity.capitalize(),
                callback_data=f"set_rarity:{card_id}:{universe}:{rarity}"
            )
        )

    if callback.message.text:
        await callback.message.edit_text(
            text="Выберите новую редкость для карты:",
            reply_markup=builder.as_markup()
        )
    elif callback.message.photo:
        await callback.message.edit_caption(
            caption="Выберите новую редкость для карты:",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.answer("Ошибка: невозможно редактировать это сообщение.", show_alert=True)

@admincardedit_router.callback_query(lambda c: c.data.startswith("set_rarity"))
async def set_rarity(callback: types.CallbackQuery):
    _, card_id, universe, new_rarity = callback.data.split(":")
    card_id = int(card_id)

    # Генерируем новые значения для атаки и здоровья на основе редкости
    attack = random.randint(*RARITY_RANGES[new_rarity]["attack"])
    hp = random.randint(*RARITY_RANGES[new_rarity]["hp"])

    # Обновляем редкость, атаку и здоровье карты в базе данных
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        UPDATE [{universe}]
        SET rarity = ?, attack = ?, hp = ?
        WHERE card_id = ?
        """, (new_rarity, attack, hp, card_id))
        conn.commit()

    # Обновляем сообщение с подтверждением
    await callback.message.edit_caption(
        caption=(
            f"Редкость карты успешно изменена на {new_rarity.capitalize()}.\n\n"
            f"Новые характеристики:\n"
            f"⚔️ Атака: {attack}\n"
            f"❤️ Здоровье: {hp}"
        ),
        reply_markup=None
    )
    await callback.answer("Редкость и характеристики обновлены.", show_alert=True)

@admincardedit_router.callback_query(EditCardCallback.filter(F.action == "edit_points"))
async def edit_points(callback: types.CallbackQuery, callback_data: EditCardCallback, state: FSMContext):
    card_id = callback_data.card_id
    universe = callback_data.universe

    await state.update_data(card_id=card_id, universe=universe)
    await callback.message.edit_caption(
        caption="Введите новое количество очков для карты:",
        reply_markup=None
    )
    await state.set_state(EditPointsState.waiting_for_points)
    await callback.answer()

@admincardedit_router.message(EditPointsState.waiting_for_points)
async def set_points(message: types.Message, state: FSMContext):
    data = await state.get_data()
    card_id = data.get("card_id")
    universe = data.get("universe")

    try:
        new_points = int(message.text)
    except ValueError:
        await message.answer("Ошибка: введите числовое значение.")
        return

    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        UPDATE [{universe}]
        SET points = ?
        WHERE card_id = ?
        """, (new_points, card_id))
        conn.commit()

    await message.answer(f"Очки карты успешно изменены на {new_points}.")
    await state.clear()

@admincardedit_router.callback_query(EditCardCallback.filter(F.action == "delete"))
async def delete_card(callback: types.CallbackQuery, callback_data: EditCardCallback):
    card_id = callback_data.card_id
    universe = callback_data.universe

    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()

        # Получаем путь к изображению карты
        cursor.execute(f"SELECT photo_path FROM [{universe}] WHERE card_id = ?", (card_id,))
        result = cursor.fetchone()

        if result:
            photo_path = result[0]
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except Exception as e:
                    print(f"Ошибка при удалении файла {photo_path}: {e}")

        # Удаляем карту из базы данных
        cursor.execute(f"DELETE FROM [{universe}] WHERE card_id = ?", (card_id,))
        conn.commit()

    await callback.message.edit_caption(
        caption="Карта успешно удалена.",
        reply_markup=None
    )
    await callback.answer("Карта удалена.", show_alert=True)