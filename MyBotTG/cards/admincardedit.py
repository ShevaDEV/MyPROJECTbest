from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from handlers.cardshand.callbackcards import EditCardCallback
import sqlite3

admincardedit_router = Router()

# Определяем состояния для FSM
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

    # Проверяем, есть ли текст или фотография в сообщении
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
    # Разбираем данные из callback_data
    _, card_id, universe, new_rarity = callback.data.split(":")
    card_id = int(card_id)

    # Обновляем редкость карты в базе данных
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        UPDATE [{universe}]
        SET rarity = ?
        WHERE card_id = ?
        """, (new_rarity, card_id))
        conn.commit()

    # Обновляем сообщение с подтверждением
    await callback.message.edit_caption(
        caption=f"Редкость карты успешно изменена на {new_rarity.capitalize()}.",
        reply_markup=None
    )
    await callback.answer("Редкость обновлена.", show_alert=True)

@admincardedit_router.callback_query(EditCardCallback.filter(F.action == "edit_points"))
async def edit_points(callback: types.CallbackQuery, callback_data: EditCardCallback, state: FSMContext):
    card_id = callback_data.card_id
    universe = callback_data.universe

    # Сохраняем данные карты в FSM
    await state.update_data(card_id=card_id, universe=universe)

    # Запрашиваем новое значение очков
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

    # Обновляем очки карты в базе данных
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

    # Удаляем карту из базы данных
    with sqlite3.connect("bot_database.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM [{universe}] WHERE card_id = ?", (card_id,))
        conn.commit()

    await callback.message.edit_caption(
        caption="Карта успешно удалена.",
        reply_markup=None
    )
    await callback.answer("Карта удалена.", show_alert=True)
