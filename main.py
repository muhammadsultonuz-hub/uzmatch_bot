import os
from aiohttp import web
import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties

TOKEN = "8938707382:AAGA_7nLTPwpkXA7_kcg0cbIo2gnAy7-QFQ"

# Tarmoq uzilishlari va timeout oldini olish uchun sessiyani sozlaymiz
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

class ProfileStates(StatesGroup):
    name = State()
    age = State()
    city = State()
    gender = State()
    photo = State()
    bio = State()

def get_db():
    return sqlite3.connect("dating_bot.db")

# /start buyrug'i
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🔍 Anketalarni qidirish")],
                [types.KeyboardButton(text="👤 Mening anketam"), types.KeyboardButton(text="🗑 Anketani o'chirish")]
            ],
            resize_keyboard=True
        )
        await message.answer("Siz ro'yxatdan o'tgansiz! Quyidagi tugmalardan birini tanlang:", reply_markup=keyboard)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Bekor qilish", callback_data="cancel_reg")
        
        await message.answer("Salom! Tanishuv botiga xush kelibsiz ❤️\n\nAnketangizni tuzamiz. Ismingiz nima?", reply_markup=builder.as_markup())
        await state.set_state(ProfileStates.name)

# Mening anketamni ko'rsatish
@dp.message(F.text == "👤 Mening anketam")
async def show_my_profile(message: types.Message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, age, city, gender, bio, photo FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await message.answer("Siz hali anketa to'ldirmagansiz. /start ni bosing.")
        return
        
    name, age, city, gender, bio, photo = user
    caption = f"Sizning anketangiz:\n\n👤 {name}, {age}, {city} 📍\n{gender}\n\n📝 {bio}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Anketani tahrirlash", callback_data="edit_profile")
    builder.button(text="🗑 O'chirish", callback_data="delete_profile")
    builder.adjust(1)
    
    await message.answer_photo(photo=photo, caption=caption, reply_markup=builder.as_markup())

# Tahrirlash
@dp.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Anketani yangilash uchun ma'lumotlarni qaytadan kiritamiz.\n\nIsmingiz nima?")
    await state.set_state(ProfileStates.name)

# Anketani o'chirish
@dp.message(F.text == "🗑 Anketani o'chirish")
@dp.callback_query(F.data == "delete_profile")
async def delete_profile(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    message = event if isinstance(event, types.Message) else event.message
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM likes WHERE user_id = ? OR target_id = ?", (user_id, user_id))
    conn.commit()
    conn.close()
    
    keyboard = types.ReplyKeyboardRemove()
    if isinstance(event, types.CallbackQuery):
        await event.message.delete()
        
    await message.answer("❌ Anketangiz bazadan o'chirib yuborildi. Qaytadan boshlash uchun /start ni bosing.", reply_markup=keyboard)

# FSM qadamlari
@dp.message(ProfileStates.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Orqaga", callback_data="back_to_name")
    await message.answer("Yoshingiz nechada? (Faqat raqam yozing)", reply_markup=builder.as_markup())
    await state.set_state(ProfileStates.age)

@dp.callback_query(F.data == "back_to_name")
async def back_to_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Ismingizni qaytadan kiriting:")
    await state.set_state(ProfileStates.name)

@dp.message(ProfileStates.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, yoshingizni faqat raqamlar bilan kiriting!")
        return
    await state.update_data(age=int(message.text))
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Orqaga", callback_data="back_to_age")
    await message.answer("Qaysi shahrdansiz? (Masalan: Andijon, Toshkent)", reply_markup=builder.as_markup())
    await state.set_state(ProfileStates.city)

@dp.callback_query(F.data == "back_to_age")
async def back_to_age(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Yoshingizni qaytadan kiriting (raqamda):")
    await state.set_state(ProfileStates.age)

@dp.message(ProfileStates.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Erkak 🚹"), types.KeyboardButton(text="Ayol 🚺")],
                  [types.KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Jinsingizni tanlang:", reply_markup=keyboard)
    await state.set_state(ProfileStates.gender)

@dp.message(ProfileStates.gender)
async def process_gender(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await message.answer("Shahringizni kiriting:")
        await state.set_state(ProfileStates.city)
        return
    if message.text not in ["Erkak 🚹", "Ayol 🚺"]:
        await message.answer("Tugmalardan birini bosing!")
        return
    await state.update_data(gender=message.text)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("O'zingizga yoqqan bitta rasmingizni yuboring:", reply_markup=keyboard)
    await state.set_state(ProfileStates.photo)

@dp.message(ProfileStates.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("O'zingiz haqingizda qisqacha ma'lumot yozing (Bio):", reply_markup=keyboard)
    await state.set_state(ProfileStates.bio)

@dp.message(ProfileStates.bio)
async def process_bio(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await message.answer("Iltimos, rasmingizni qaytadan yuboring:")
        await state.set_state(ProfileStates.photo)
        return

    data = await state.get_data()
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, name, age, city, gender, bio, photo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data['name'], data['age'], data['city'], data['gender'], message.text, data['photo']))
    conn.commit()
    conn.close()
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔍 Anketalarni qidirish")],
            [types.KeyboardButton(text="👤 Mening anketam"), types.KeyboardButton(text="🗑 Anketani o'chirish")]
        ],
        resize_keyboard=True
    )
    await message.answer("✅ Anketangiz muvaffaqiyatli saqlandi!", reply_markup=keyboard)
    await state.clear()

# --- Qidirish menyusi klaviaturasi ---
search_keyboard = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="❤️ Yoqdi"), types.KeyboardButton(text="👎 Yoqmadi")],
        [types.KeyboardButton(text="🔙 Orqaga")]
    ],
    resize_keyboard=True
)

# --- Anketalarni qidirish ---
@dp.message(F.text == "🔍 Anketalarni qidirish")
@dp.message(Command("search"))
async def search_profiles(message: types.Message):
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT gender, city FROM users WHERE user_id = ?", (user_id,))
    my_profile = cursor.fetchone()
    
    if not my_profile:
        conn.close()
        await message.answer("Oldin o'z anketangizni to'ldirishingiz kerak. /start ni bosing.")
        return
        
    my_gender, my_city = my_profile
    target_gender = "Ayol 🚺" if my_gender == "Erkak 🚹" else "Erkak 🚹"
    
    cursor.execute("""
        SELECT user_id, name, age, city, gender, bio, photo 
        FROM users 
        WHERE user_id != ? AND gender = ?
        ORDER BY RANDOM() LIMIT 1
    """, (user_id, target_gender))
    
    candidate = cursor.fetchone()
    
    if not candidate:
        cursor.execute("""
            SELECT user_id, name, age, city, gender, bio, photo 
            FROM users 
            WHERE user_id != ? 
            ORDER BY RANDOM() LIMIT 1
        """, (user_id,))
        candidate = cursor.fetchone()
        
    conn.close()
        
    if not candidate:
        await message.answer("Hozircha bazada boshqa anketalar yo'q. 😔")
        return
        
    cand_id, name, age, city, gender, bio, photo = candidate
    caption = f"👤 {name}, {age} yosh, {city} 📍\n{gender}\n\n📝 {bio}\n\n🆔_ID:{cand_id}"
    
    await message.answer_photo(photo=photo, caption=caption, reply_markup=search_keyboard)

# --- "❤️ Yoqdi" bosilganda ---
@dp.message(F.text == "❤️ Yoqdi")
async def process_like_text(message: types.Message):
    await message.answer("❤️")
    await search_profiles(message)

# --- "👎 Yoqmadi" bosilganda ---
@dp.message(F.text == "👎 Yoqmadi")
async def process_dislike_text(message: types.Message):
    await search_profiles(message)

# --- "🔙 Orqaga" bosilganda ---
@dp.message(F.text == "🔙 Orqaga")
async def process_back_text(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔍 Anketalarni qidirish")],
            [types.KeyboardButton(text="👤 Mening anketam"), types.KeyboardButton(text="🗑 Anketani o'chirish")]
        ],
        resize_keyboard=True
    )
    await message.answer("Asosiy menyu:", reply_markup=keyboard)

# --- Render uchun mini web-server ---
async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.router.add_get("/", handle)

async def web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- Asosiy ishga tushirish funksiyasi ---
async def main():
    # 1. Web-serverni ishga tushiramiz (Render port talabini qondirish uchun)
    await web_server()
    print("Web-server muvaffaqiyatli ishga tushdi...")
    
    # 2. Telegram botni ishga tushiramiz
    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())