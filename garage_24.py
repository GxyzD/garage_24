import sqlite3
import logging
import random
import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

logging.basicConfig(level=logging.INFO)

con = sqlite3.connect('players.db')
cur = con.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    balance INTEGER,
    inventory TEXT
)
''')
con.commit()

token = "5650778080:AAGtXI1erI-nwmJVXH9GQ0n3miu8My-rCHM"

bot = Bot(token=token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

class InventoryState(StatesGroup):
    viewing = State()

class BattleState(StatesGroup):
    waiting_for_opponent = State()
    in_battle = State()
    choosing_card = State()

card_score_map = {
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTu9J9tLfZ7Qgvl-rHIrMksuZjONDjoA8AQQjRaMijG428tgRqhTH2AERahR_Diz5w-XYc&usqp=CAU": 3,  # Very rare
    "https://cdna.artstation.com/p/assets/images/images/032/531/200/large/samir-djafarov-m4g82-360-5.jpg?1606736833": 2,  # Rare
    "https://www.supercarclub.pl/wp-content/uploads/2021/11/Porsche-911-992-GT3-1-scaled.jpg": 2,  # Rare
    "https://images.drive.ru/i/0/5fabaa40ec05c4a31100011d.jpg": 1,  # Uncommon
}

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_username = message.from_user.username

    cur.execute("SELECT * FROM players WHERE username = ?", (user_username,))
    result = cur.fetchone()

    if result is None:
        balance = 300
        inventory = json.dumps([])
        cur.execute("INSERT INTO players (username, balance, inventory) VALUES (?, ?, ?)",
                    (user_username, balance, inventory))
        con.commit()

    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Get card 🎁  Стоимость карты - 50")],
            [KeyboardButton(text="Battle ⚔")],
            [KeyboardButton(text="Inventory 🎒")],
            [KeyboardButton(text="Information ⚙")]
        ],
        resize_keyboard=True
    )

    photo_url = "https://1neperformance.com/cdn/shop/products/165065911_4507583475923890_5787636887567303850_n_1024x1024_2x_jpg_590x.jpg?v=1648868058"

    await bot.send_photo(
        chat_id=message.chat.id,
        photo=photo_url,
        caption="Добро пожаловать в игру!",
        reply_markup=reply_keyboard
    )

@router.message(lambda message: message.text == "Get card 🎁  Стоимость карты - 50")
async def send_get_card(message: types.Message):
    user_username = message.from_user.username

    cur.execute("SELECT balance, inventory FROM players WHERE username = ?", (user_username,))
    result = cur.fetchone()

    if result is None:
        await bot.send_message(message.chat.id, "Пользователь не найден в базе данных.")
        return
    
    balance, inventory = result

    new_balance = balance - 50
    if new_balance < 0:
        await bot.send_message(message.chat.id, "Недостаточно средств.")
        return

    cur.execute("UPDATE players SET balance = ? WHERE username = ?", (new_balance, user_username))
    con.commit()

    await bot.send_message(message.chat.id, 'Ваша новая карта!!!')

    card_url = ""
    caption = "Поздравляем! Вы получили карту!"
    
    rand_val = random.random()
    if rand_val <= 0.01:
        card_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTu9J9tLfZ7Qgvl-rHIrMksuZjONDjoA8AQQjRaMijG428tgRqhTH2AERahR_Diz5w-XYc&usqp=CAU"
        rarity = "very_rare"
        caption = "Поздравляем! Вы получили очень редкую карту!"
    elif rand_val <= 0.26:
        card_url = "https://cdna.artstation.com/p/assets/images/images/032/531/200/large/samir-djafarov-m4g82-360-5.jpg?1606736833"
        rarity = "rare"
        caption = "Поздравляем! Вы получили редкую карту!"
    elif rand_val <= 0.51:
        card_url = "https://www.supercarclub.pl/wp-content/uploads/2021/11/Porsche-911-992-GT3-1-scaled.jpg"
        rarity = "rare"
        caption = "Поздравляем! Вы получили редкую карту!"
    else:
        card_url = "https://images.drive.ru/i/0/5fabaa40ec05c4a31100011d.jpg"
        rarity = "uncommon"
    
    await bot.send_photo(message.chat.id, card_url, caption=caption)
    
    inventory_list = json.loads(inventory)
    inventory_list.append(card_url)
    new_inventory = json.dumps(inventory_list)
    
    cur.execute("UPDATE players SET inventory = ? WHERE username = ?", (new_inventory, user_username))
    con.commit()

    await bot.send_message(message.chat.id, f"Ваш новый баланс: {new_balance}")

@router.message(lambda message: message.text == "Inventory 🎒")
async def show_inventory(message: types.Message, state: FSMContext):
    cur.execute("SELECT inventory FROM players WHERE username = ?", (message.from_user.username,))
    result = cur.fetchone()
    
    if result is None:
        await bot.send_message(message.chat.id, "Пользователь не найден в базе данных.")
        return
    
    inventory = json.loads(result[0])
    if not inventory:
        await bot.send_message(message.chat.id, "Ваш инвентарь пуст.")
        return
    
    await state.update_data(inventory=inventory, current_index=0)
    
    await show_current_item(message.chat.id, state, new_message=True)

async def show_current_item(chat_id: int, state: FSMContext, new_message=False):
    data = await state.get_data()
    inventory = data['inventory']
    current_index = data['current_index']
    
    item = inventory[current_index]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="prev_item"),
            InlineKeyboardButton(text="➡️", callback_data="next_item")
        ]
    ])
    
    caption = f"Карта {current_index + 1}/{len(inventory)}"
    
    if new_message:
        sent_message = await bot.send_photo(chat_id, item, caption=caption, reply_markup=keyboard)
        await state.update_data(inventory_message_id=sent_message.message_id)
    else:
        message_id = data['inventory_message_id']
        await bot.edit_message_media(
            media=InputMediaPhoto(media=item, caption=caption),
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=keyboard
        )

@router.callback_query(lambda c: c.data == 'prev_item')
async def prev_item(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id, show_alert=False, cache_time=0)
    data = await state.get_data()
    current_index = data['current_index']
    new_index = current_index - 1
    if new_index < 0:
        new_index = 0
    await state.update_data(current_index=new_index)
    await show_current_item(callback.message.chat.id, state)

@router.callback_query(lambda c: c.data == 'next_item')
async def next_item(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id, show_alert=False, cache_time=0)
    data = await state.get_data()
    current_index = data['current_index']
    new_index = current_index + 1
    if new_index >= len(data['inventory']):
        new_index = len(data['inventory']) - 1
    await state.update_data(current_index=new_index)
    await show_current_item(callback.message.chat.id, state)

@router.message(lambda message: message.text == "Battle ⚔")
async def initiate_battle(message: types.Message, state: FSMContext):
    await state.set_state(BattleState.waiting_for_opponent)
    await bot.send_message(message.chat.id, "Введите имя пользователя соперника для начала сражения:")

@router.message(StateFilter(BattleState.waiting_for_opponent))
async def handle_opponent_username(message: types.Message, state: FSMContext):
    opponent_username = message.text.strip()
    user_username = message.from_user.username
    
    if opponent_username == user_username:
        await bot.send_message(message.chat.id, "Вы не можете сражаться сами с собой.")
        return

    cur.execute("SELECT id FROM players WHERE username = ?", (opponent_username,))
    result = cur.fetchone()

    if result is None:
        await bot.send_message(message.chat.id, "Соперник не найден в базе данных.")
        return

    opponent_id = result[0]

    await state.update_data(opponent=opponent_username, opponent_id=opponent_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Принять вызов", callback_data="accept_battle")]
    ])

    await bot.send_message(
        opponent_id,
        f"{user_username} вызывает вас на битву! Примите вызов?",
        reply_markup=keyboard
    )

    await bot.send_message(message.chat.id, f"Ожидаем ответа от {opponent_username}...")

def get_card_score(card_url: str) -> int:
    return card_score_map.get(card_url, 0)

@router.callback_query(lambda c: c.data == "choose_this_card")
async def choose_this_card(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']
    inventory = data['inventory']
    card_url = inventory[current_index]
    await state.update_data(player_card=card_url)

    await bot.send_message(callback.message.chat.id, "Карта выбрана. Ожидаем выбора карты соперником...")

    await state.set_state(BattleState.in_battle)

@router.callback_query(lambda c: c.data == "accept_battle")
async def accept_battle(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    opponent_username = callback.from_user.username
    opponent_id = callback.from_user.id
    user_username = data.get('opponent')

    await state.update_data(opponent_card_message_id=callback.message.message_id)
    await bot.edit_message_text("Вы приняли вызов! Выберите карту для битвы.", opponent_id, callback.message.message_id)

    cur.execute("SELECT inventory FROM players WHERE username = ?", (opponent_username,))
    result = cur.fetchone()

    if result is None:
        await bot.send_message(opponent_id, "Ошибка: инвентарь не найден.")
        return

    inventory = json.loads(result[0])
    if not inventory:
        await bot.send_message(opponent_id, "Ваш инвентарь пуст.")
        return

    await state.update_data(inventory=inventory, current_index=0)
    await show_current_item(opponent_id, state, new_message=True)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать эту карту", callback_data="choose_this_card_opponent")]
    ])

    await bot.send_message(opponent_id, "Выберите карту для битвы.", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "choose_this_card_opponent")
async def choose_this_card_opponent(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']
    inventory = data['inventory']
    card_url = inventory[current_index]
    opponent_username = callback.from_user.username
    opponent_id = callback.from_user.id
    user_username = data.get('opponent')

    await state.update_data(opponent_card=card_url)
    await bot.edit_message_text("Карта выбрана. Начинаем битву!", opponent_id, data['opponent_card_message_id'])

    cur.execute("SELECT id FROM players WHERE username = ?", (user_username,))
    result = cur.fetchone()

    if result is None:
        await bot.send_message(opponent_id, "Ошибка: пользователь не найден.")
        return

    user_id = result[0]
    await bot.send_message(user_id, f"Ваш соперник {opponent_username} выбрал карту для битвы. Начинаем сражение!")

    await perform_battle(user_id, opponent_id, state)

async def perform_battle(user_id: int, opponent_id: int, state: FSMContext):
    data = await state.get_data()
    player_card = data.get('player_card')
    opponent_card = data.get('opponent_card')

    if not player_card or not opponent_card:
        await bot.send_message(user_id, "Ошибка определения карт.")
        await bot.send_message(opponent_id, "Ошибка определения карт.")
        return

    player_card_score = get_card_score(player_card)
    opponent_card_score = get_card_score(opponent_card)

    if player_card_score is None or opponent_card_score is None:
        await bot.send_message(user_id, "Ошибка определения редкости карты.")
        await bot.send_message(opponent_id, "Ошибка определения редкости карты.")
        return

    if player_card_score > opponent_card_score:
        result_message = "Вы победили в битве!"
        opponent_result_message = "Вы проиграли битву."
    elif player_card_score < opponent_card_score:
        result_message = "Вы проиграли битву."
        opponent_result_message = "Вы победили в битве!"
    else:
        result_message = "Битва закончилась ничьей."
        opponent_result_message = "Битва закончилась ничьей."

    await bot.send_message(user_id, f"Ваша карта: {player_card}\nКарта соперника: {opponent_card}\n\n{result_message}")
    await bot.send_message(opponent_id, f"Ваша карта: {opponent_card}\nКарта соперника: {player_card}\n\n{opponent_result_message}")

@router.message(lambda message: message.text == "Information ⚙")
async def show_information(message: types.Message):
    await bot.send_message(message.chat.id, "Информация о боте...")

if __name__ == "__main__":
    dp.run_polling(bot)