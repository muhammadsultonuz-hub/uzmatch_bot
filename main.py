import os
from aiohttp import web
import logging
import sqlite3
import asyncio
import base64
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession

TOKEN = "8938707382:AAGA_7nLTPwpkXA7_kcg0cbIo2gnAy7-QFQ"
PAYME_MERCHANT_ID = "SIZNING_PAYME_MERCHANT_ID"  # Hisob raqam tayyor bo'lgach haqiqiy ID yoziladi
ADMIN_ID = 5985235760  # O'zingizning Telegram ID raqamingizni yozing (Admin uchun)

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

def init_db():
    conn = sqlite3.connect("dating_bot.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            gender TEXT,
            bio TEXT,
            photo TEXT,
            vip_expires TIMESTAMP,
            last_viewed_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            user_id INTEGER,
            target_id INTEGER
        )
    ''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_viewed_id INTEGER")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN vip_expires TIMESTAMP")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'pending'")
    except Exception:
        pass
    conn.commit()
    conn.close()

init_db()

# Asosiy menyu klaviaturasi
def get_main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔍 Anketalarni qidirish")],
            [types.KeyboardButton(text="❤️ Meni yoqtirganlar")],
            [types.KeyboardButton(text="👤 Mening anketam"), types.KeyboardButton(text="🗑 Anketani o'chirish")],
            [types.KeyboardButton(text="👑 VIP status olish")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        await message.answer("Siz ro'yxatdan o'tgansiz! Quyidagi tugmalardan birini tanlang:", reply_markup=get_main_keyboard())
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Bekor qilish", callback_data="cancel_reg")
        await message.answer("Salom! Tanishuv botiga xush kelibsiz ❤️\n\nAnketangizni tuzamiz. Ismingiz nima?", reply_markup=builder.as_markup())
        await state.set_state(ProfileStates.name)

@dp.message(F.text == "👤 Mening anketam")
async def show_my_profile(message: types.Message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, age, city, gender, bio, photo, vip_expires, status FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await message.answer("Siz hali anketa to'ldirmagansiz. /start ni bosing.")
        return
        
    name, age, city, gender, bio, photo, vip_expires, status = user
    
    status_text = "⏳ Tekshiruvda" if status == 'pending' else ("✅ Tasdiqlangan" if status == 'approved' else "❌ Rad etilgan")

    vip_status = "❌ Yo'q"
    if vip_expires:
        try:
            exp_date = datetime.strptime(vip_expires, "%Y-%m-%d %H:%M:%S")
            if exp_date > datetime.now():
                vip_status = f"✅ Faol ({exp_date.strftime('%d.%m.%Y')} gacha)"
        except Exception:
            pass

    caption = f"Sizning anketangiz:\n\n👤 {name}, {age}, {city} 📍\n{gender}\n\n📝 {bio}\n\n📌 Holati: {status_text}\n👑 VIP status: {vip_status}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Anketani tahrirlash", callback_data="edit_profile")
    builder.button(text="🗑 O'chirish", callback_data="delete_profile")
    builder.adjust(1)
    
    await message.answer_photo(photo=photo, caption=caption, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Anketani yangilash uchun ma'lumotlarni qaytadan kiritamiz.\n\nIsmingiz nima?")
    await state.set_state(ProfileStates.name)

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
        INSERT OR REPLACE INTO users (user_id, name, age, city, gender, bio, photo, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (user_id, data['name'], data['age'], data['city'], data['gender'], message.text, data['photo']))
    conn.commit()
    conn.close()
    
    # Foydalanuvchiga darhol menyuni chiqaramiz va botdan foydalanishiga ruxsat beramiz
    await message.answer("✅ Anketangiz saqlandi va tekshiruv uchun adminga yuborildi!\n\nSiz hozircha botdan foydalanib turishingiz mumkin:", reply_markup=get_main_keyboard())
    await state.clear()

    # Admin'ga moderatsiya uchun yuborish
    if ADMIN_ID:
        admin_kb = InlineKeyboardBuilder()
        admin_kb.button(text="✅ Tasdiqlash", callback_data=f"adm_yes_{user_id}")
        admin_kb.button(text="❌ Rad etish", callback_data=f"adm_no_{user_id}")
        admin_kb.adjust(2)
        
        caption = (
            f"🔔 **Yangi anketa tekshiruv uchun keldi!**\n\n"
            f"👤 {data['name']}, {data['age']} yosh, {data['city']} 📍\n"
            f"{data['gender']}\n\n"
            f"📝 {message.text}"
        )
        try:
            await bot.send_photo(chat_id=ADMIN_ID, photo=data['photo'], caption=caption, reply_markup=admin_kb.as_markup(), parse_mode="Markdown")
        except Exception:
            pass

# Admin qarori uchun handler
@dp.callback_query(F.data.startswith("adm_"))
async def admin_decision(callback: types.CallbackQuery):
    action, target_user_id = callback.data.split("_")[1], int(callback.data.split("_")[2])
    
    conn = get_db()
    cursor = conn.cursor()
    if action == "yes":
        cursor.execute("UPDATE users SET status = 'approved' WHERE user_id = ?", (target_user_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ **HOLAT: Tasdiqlandi**", parse_mode="Markdown")
        try:
            await bot.send_message(target_user_id, "🎉 Tabriklaymiz! Anketangiz admin tomonidan tasdiqlandi va umumiy qidiruvga qo'shildi.")
        except Exception:
            pass
    else:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (target_user_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ **HOLAT: Rad etildi va o'chirildi**", parse_mode="Markdown")
        try:
            await bot.send_message(target_user_id, "❌ Afsuski, anketangiz talablarga javob bermagani uchun rad etildi. /start orqali qaytadan urinib ko'rishingiz mumkin.")
        except Exception:
            pass
    await callback.answer("Bajarildi!")

# --- VIP obuna va Payme to'lov qismi ---
@dp.message(F.text == "👑 VIP status olish")
async def cmd_vip(message: types.Message):
    await show_vip_tariffs(message)

async def show_vip_tariffs(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 10 kun — 15,000 UZS", callback_data="buy_vip_10")
    builder.button(text="💎 20 kun — 30,000 UZS", callback_data="buy_vip_20")
    builder.button(text="💎 30 kun — 40,000 UZS", callback_data="buy_vip_30")
    builder.adjust(1)
    
    text = (
        "👑 **VIP status imkoniyatlari:**\n\n"
        "• Shaxsiy chatlarni ochish\n"
        "• Kimlar sizni yoqtirganini ko'rish\n"
        "• Cheksiz qidiruv imkoniyati\n\n"
        "O'zingizga mos tarifni tanlang va Payme orqali to'lang:"
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_vip_"))
async def process_buy_vip(callback: types.CallbackQuery):
    days_map = {
        "buy_vip_10": (10, 1500000, "10 kunlik VIP"),
        "buy_vip_20": (20, 3000000, "20 kunlik VIP"),
        "buy_vip_30": (30, 4000000, "30 kunlik VIP")
    }
    
    data_key = callback.data
    if data_key not in days_map:
        return
        
    days, amount_tiyin, title = days_map[data_key]
    user_id = callback.from_user.id
    
    raw_data = f"m={PAYME_MERCHANT_ID};ac.user_id={user_id};ac.days={days};a={amount_tiyin}"
    encoded_data = base64.b64encode(raw_data.encode("utf-8")).decode("utf-8")
    payme_link = f"https://checkout.payme.uz/{encoded_data}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Payme orqali to'lash", url=payme_link)
    
    await callback.message.answer(
        f"💳 **{title}** uchun to'lov havolasi tayyor!\n\n"
        f"Summa: **{amount_tiyin // 100} UZS**\n\n"
        f"Tugmani bosing va to'lovni amalga oshiring. To'lov tasdiqlangandan so'ng VIP avtomatik yoqiladi.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- Meni yoqtirganlar bo'limi (Anketa tasdiqlanmagan bo'lsa ham ishlaydi) ---
@dp.message(F.text == "❤️ Meni yoqtirganlar")
async def show_who_liked_me(message: types.Message):
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT vip_expires FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    is_vip = False
    if row and row[0]:
        try:
            exp_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if exp_date > datetime.now():
                is_vip = True
        except Exception:
            pass
            
    if not is_vip:
        conn.close()
        builder = InlineKeyboardBuilder()
        builder.button(text="👑 VIP status olish", callback_data="buy_vip_menu")
        await message.answer(
            "🔒 **Diqqat!** Sizga kimlar layk bosganini ko'rish uchun **VIP status** talab etiladi.\n\n"
            "VIP statusni oling va o'zingizga yoqlarini darhol toping:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return

    # Statusidan qat'i nazar unga layk bosganlarni ko'rsatamiz
    cursor.execute("""
        SELECT u.user_id, u.name, u.age, u.city, u.gender, u.bio, u.photo
        FROM likes l
        JOIN users u ON l.user_id = u.user_id
        WHERE l.target_id = ?
        ORDER BY l.rowid DESC LIMIT 1
    """, (user_id,))
    fan = cursor.fetchone()
    conn.close()

    if not fan:
        await message.answer("Hozircha sizga hech kim layk bosmagan. Qidiruvni davom eting! 🔍")
        return

    f_id, name, age, city, gender, bio, photo = fan
    caption = f"💖 **Sizga bu inson yoqdi!**\n\n👤 {name}, {age} yosh, {city} 📍\n{gender}\n\n📝 {bio}"

    inline_kb = InlineKeyboardBuilder()
    inline_kb.button(text="💬 Chatga o'tish", url=f"tg://user?id={f_id}")

    await message.answer_photo(photo=photo, caption=caption, reply_markup=inline_kb.as_markup(), parse_mode="Markdown")

# --- Qidirish menyusi (Shahri bo'yicha filtr bilan) ---
@dp.message(F.text == "🔍 Anketalarni qidirish")
@dp.message(Command("search"))
async def start_search_cmd(message: types.Message):
    reply_kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="❤️"), types.KeyboardButton(text="👎")],
            [types.KeyboardButton(text="🔙 Orqaga")]
        ],
        resize_keyboard=True
    )
    await message.answer("🔍 Qidiruv boshlandi:", reply_markup=reply_kb)
    await search_profiles(message)

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

    # 1. Avval faqat TASDIQLANGAN ('approved') va bir xil shahrdagi foydalanuvchilarni qidiramiz
    cursor.execute("""
        SELECT user_id, name, age, city, gender, bio, photo
        FROM users
        WHERE user_id != ? AND gender = ? AND city = ? AND status = 'approved'
        ORDER BY RANDOM() LIMIT 1
    """, (user_id, target_gender, my_city))
    candidate = cursor.fetchone()

    # 2. Agar o'sha shahardan topilmasa, boshqa shahrlardagi tasdiqlanganlarini chiqaramiz
    if not candidate:
        cursor.execute("""
            SELECT user_id, name, age, city, gender, bio, photo
            FROM users
            WHERE user_id != ? AND gender = ? AND status = 'approved'
            ORDER BY RANDOM() LIMIT 1
        """, (user_id, target_gender))
        candidate = cursor.fetchone()

    if not candidate:
        conn.close()
        await message.answer("Hozircha mos keladigan boshqa anketalar yo'q. 😔")
        return

    cand_id, name, age, city, gender, bio, photo = candidate

    cursor.execute("UPDATE users SET last_viewed_id = ? WHERE user_id = ?", (cand_id, user_id))
    conn.commit()
    conn.close()

    caption = f"👤 {name}, {age} yosh, {city} 📍\n{gender}\n\n📝 {bio}"

    inline_kb = InlineKeyboardBuilder()
    inline_kb.button(text="💬 Shaxsiy chatga kirish uchun havola", callback_data=f"chat_link_{cand_id}")

    await message.answer_photo(photo=photo, caption=caption, reply_markup=inline_kb.as_markup())

# --- Chat tugmasi bosilganda VIP ni tekshirish ---
@dp.callback_query(F.data.startswith("chat_link_"))
async def process_chat_link(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    target_id = int(callback.data.split("_")[2])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT vip_expires FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    is_vip = False
    if row and row[0]:
        try:
            exp_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if exp_date > datetime.now():
                is_vip = True
        except Exception:
            pass
            
    if is_vip:
        builder = InlineKeyboardBuilder()
        builder.button(text="💬 Chatga o'tish", url=f"tg://user?id={target_id}")
        await callback.message.answer("✨ Sizda VIP status mavjud! Marhamat, chatga o'ting:", reply_markup=builder.as_markup())
        await callback.answer()
    else:
        await callback.answer("🔒 Chatni ochish uchun VIP status olishingiz kerak!", show_alert=True)
        builder = InlineKeyboardBuilder()
        builder.button(text="👑 VIP status olish", callback_data="buy_vip_menu")
        await callback.message.answer(
            "🔒 **Diqqat!** Shaxsiy chatga kirish va boshqalar bilan muloqot qilish uchun **VIP status** talab etiladi.\n\n"
            "VIP statusni sotib oling va barcha cheklovlarni olib tashlang:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data == "buy_vip_menu")
async def process_buy_vip_menu(callback: types.CallbackQuery):
    await show_vip_tariffs(callback.message)
    await callback.answer()

# --- Pastdan "❤️" bosilganda ---
@dp.message(F.text == "❤️")
async def process_heart_like(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_viewed_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row or not row[0]:
        conn.close()
        await search_profiles(message)
        return
        
    target_id = row[0]
    
    cursor.execute("SELECT * FROM likes WHERE user_id = ? AND target_id = ?", (user_id, target_id))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO likes (user_id, target_id) VALUES (?, ?)", (user_id, target_id))
        conn.commit()
    conn.close()

    await message.answer("❤️ Yoqtirildi!")
    await search_profiles(message)

# --- Pastdan "👎" bosilganda ---
@dp.message(F.text == "👎")
async def process_thumb_dislike(message: types.Message):
    await search_profiles(message)

# --- "🔙 Orqaga" bosilganda ---
@dp.message(F.text == "🔙 Orqaga")
async def process_back_text(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_keyboard())

# --- Render uchun mini web-server va Payme Webhook ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def payme_webhook(request):
    try:
        data = await request.json()
        return web.json_response({"result": {"status": 1}})
    except Exception as e:
        return web.json_response({"error": str(e)})

app = web.Application()
app.router.add_get("/", handle)
app.router.add_post("/payme", payme_webhook)

async def web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await web_server()
    print("Web-server va bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())