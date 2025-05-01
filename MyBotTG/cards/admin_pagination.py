from aiogram import Router, types
from handlers.cardshand.callbackcards import AdminPaginationCallback
from kbds.inlinecards import admin_pagination_keyboard, edit_card_keyboard
from aiogram.fsm.context import FSMContext

admin_pagination_router = Router()

@admin_pagination_router.callback_query(AdminPaginationCallback.filter())
async def paginate_admin_cards(callback: types.CallbackQuery, callback_data: AdminPaginationCallback, state: FSMContext):
    rarity_type = callback_data.rarity_type
    index = callback_data.index

    # Получаем данные для пагинации из FSMContext
    data = await state.get_data()
    cards = data.get("admin_cards")
    universe = data.get("universe")

    if not cards or not universe:
        await callback.answer("Данные для пагинации не найдены.", show_alert=True)
        return

    # Корректируем индекс
    index = index % len(cards)

    # Получаем данные для текущей карты
    card_id, name, photo_id, rarity, attack, hp, points = cards[index]

    # Формируем описание карты
    caption = (
        f"🆔 ID: {card_id}\n"
        f"🏷️ Имя: {name}\n"
        f"🎲 Редкость: {rarity.capitalize()}\n"
        f"⚔️ Атака: {attack}\n"
        f"❤️ Здоровье: {hp}\n"
        f"💎 Очки: {points}\n"
    )

    # Кнопки пагинации
    pagination_markup = admin_pagination_keyboard(rarity=rarity_type, index=index, total=len(cards))

    # Кнопки редактирования
    edit_kb = edit_card_keyboard(card_id=card_id, universe=universe)

    # Обновляем сообщение с картой
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo_id, caption=caption),
            reply_markup=pagination_markup
        )
        # Отправляем кнопки редактирования отдельно
        await callback.message.answer("Выберите действие для карты:", reply_markup=edit_kb)
    except Exception as e:
        print(f"Ошибка при обновлении карты: {e}")
        await callback.answer("Произошла ошибка при переключении карт.", show_alert=True)

    await callback.answer()