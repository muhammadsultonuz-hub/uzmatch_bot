import os
from aiohttp import web
import logging
import sqlite3
import asyncio
import base64
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.client.session.aiohttp import AiohttpSession

TOKEN = "8938707382:AAHz_kGQo5F_IjT07J1QHtFYUQTIHdfn7-Y"
PAYME_MERCHANT_ID = "SIZNING_PAYME_MERCHANT_ID"
ADMIN_ID = 5985235760

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
    
    await message.answer("✅ Anketangiz saqlandi va tekshiruv uchun adminga yuborildi!\n\nSiz hozircha botdan foydalanib turishingiz mumkin:", reply_markup=get_main_keyboard())
    await state.clear()

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

# --- VIP obuna va Ikkala to'lov tizimi (Stars va Payme) ---
@dp.message(F.text == "👑 VIP status olish")
async def cmd_vip(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐️ Telegram Stars orqali", callback_data="pay_method_stars")
    builder.button(text="💳 Karta (Payme) orqali", callback_data="pay_method_payme")
    builder.adjust(1)
    
    await message.answer(
        "👑 **VIP status imkoniyatlari:**\n\n"
        "• Shaxsiy chatlarni ochish\n"
        "• Kimlar sizni yoqtirganini ko'rish\n"
        "• Cheksiz qidiruv imkoniyati\n\n"
        "To'lov turini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "pay_method_stars")
async def choose_stars_tariffs(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐️ 7 kun — 80 Stars", callback_data="stars_vip_7")
    builder.button(text="⭐️ 14 kun — 160 Stars", callback_data="stars_vip_14")
    builder.button(text="⭐️ 30 kun — 300 Stars (Tejamkor)", callback_data="stars_vip_30")
    builder.button(text="⬅️ Orqaga", callback_data="back_to_pay_methods")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "⭐️ **Telegram Stars tariflari:**\n\nO'zingizga mos muddatni tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "pay_method_payme")
async def choose_payme_tariffs(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 7 kun — 15,000 UZS", callback_data="payme_vip_7")
    builder.button(text="💳 14 kun — 30,000 UZS", callback_data="payme_vip_14")
    builder.button(text="💳 30 kun — 45,000 UZS", callback_data="payme_vip_30")
    builder.button(text="⬅️ Orqaga", callback_data="back_to_pay_methods")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "💳 **Karta (Payme) tariflari:**\n\nO'zingizga mos muddatni tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_pay_methods")
async def back_to_pay_methods(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐️ Telegram Stars orqali", callback_data="pay_method_stars")
    builder.button(text="💳 Karta (Payme) orqali", callback_data="pay_method_payme")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "👑 **VIP status imkoniyatlari:**\n\nTo'lov turini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("stars_vip_"))
async def send_stars_invoice(callback: types.CallbackQuery):
    tariffs = {
        "stars_vip_7": (7, 80, "7 kunlik VIP status"),
        "stars_vip_14": (14, 160, "14 kunlik VIP status"),
        "stars_vip_30": (30, 300, "30 kunlik VIP status")
    }
    
    key = callback.data
    if key not in tariffs:
        return
        
    days, stars_amount, title = tariffs[key]
    prices = [LabeledPrice(label=title, amount=stars_amount)]
    
    await callback.message.answer_invoice(
        title=title,
        description=f"Tanishuv botida {days} kun davomida VIP imkoniyatlardan foydalanish.",
        prices=prices,
        provider_token="",
        payload=f"vip_{days}",
        currency="XTR"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("payme_vip_"))
async def send_payme_link(callback: types.CallbackQuery):
    tariffs = {
        "payme_vip_7": (7, 1500000, "7 kunlik VIP"),
        "payme_vip_14": (14, 3000000, "14 kunlik VIP"),
        "payme_vip_30": (30, 4500000, "30 kunlik VIP")
    }
    
    key = callback.data
    if key not in tariffs:
        return
        
    days, amount_tiyin, title = tariffs[key]
    user_id = callback.from_user.id
    
    raw_data = f"m={PAYME_MERCHANT_ID};ac.user_id={user_id};ac.days={days};a={amount_tiyin}"
    encoded_data = base64.b64encode(raw_data.encode("utf-8")).decode("utf-8")
    payme_link = f"https://checkout.payme.uz/{encoded_data}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Payme orqali to'lash", url=payme_link)
    
    await callback.message.answer(
        f"💳 **{title}** uchun to'lov havolasi tayyor!\n\n"
        f"Summa: **{amount_tiyin // 100} UZS**\n\n"
        f"Tugmani bosing va to'lovni amalga oshiring.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("vip_"):
        days = int(payload.split("_")[1])
        user_id = message.from_user.id
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT vip_expires FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        now = datetime.now()
        new_expiry = now + timedelta(days=days)
        
        if row and row[0]:
            try:
                current_expiry = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                if current_expiry > now:
                    new_expiry = current_expiry + timedelta(days=days)
            except Exception:
                pass
                
        formatted_expiry = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE users SET vip_expires = ? WHERE user_id = ?", (formatted_expiry, user_id))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"🎉 **To'lov muvaffaqiyatli qabul qilindi!**\n\n"
            f"Sizga **{days} kunlik VIP status** faollashtirildi.\n"
            f"📅 Amal qilish muddati: **{new_expiry.strftime('%d.%m.%Y %H:%M')}** gacha.",
            parse_mode="Markdown"
        )

# --- Meni yoqtirganlar bo'limi ---
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

@dp.callback_query(F.data == "buy_vip_menu")
async def process_buy_vip_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐️ Telegram Stars orqali", callback_data="pay_method_stars")
    builder.button(text="💳 Karta (Payme) orqali", callback_data="pay_method_payme")
    builder.adjust(1)
    
    await callback.message.answer(
        "👑 **VIP status imkoniyatlari:**\n\nTo'lov turini tanlang:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# --- Qidirish menyusi ---
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

    cursor.execute("""
        SELECT user_id, name, age, city, gender, bio, photo
        FROM users
        WHERE user_id != ? AND gender = ? AND city = ? AND status = 'approved'
        ORDER BY RANDOM() LIMIT 1
    """, (user_id, target_gender, my_city))
    candidate = cursor.fetchone()

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

    cursor.execute("SELECT * FROM likes WHERE user_id = ? AND target_id = ?", (target_id, user_id))
    is_match = cursor.fetchone()
    
    cursor.execute("SELECT name FROM users WHERE user_id = ?", (target_id,))
    target_user = cursor.fetchone()
    target_name = target_user[0] if target_user else "Foydalanuvchi"
    
    conn.close()

    if is_match:
        match_kb = InlineKeyboardBuilder()
        match_kb.button(text=f"💬 {target_name} bilan chatga o'tish", url=f"tg://user?id={target_id}")
        
        await message.answer(
            f"🎉 **Ajoyib! O'zaro simpatiya (Match)!**\n\n"
            f"Sizga va **{target_name}** ga bir-biringiz yoqdingiz ❤️\n"
            f"Marhamat, bepul bog'laning:",
            reply_markup=match_kb.as_markup(),
            parse_mode="Markdown"
        )
        try:
            my_conn = get_db()
            my_cursor = my_conn.cursor()
            my_cursor.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
            my_row = my_cursor.fetchone()
            my_name = my_row[0] if my_row else "Foydalanuvchi"
            my_conn.close()
            
            back_kb = InlineKeyboardBuilder()
            back_kb.button(text=f"💬 {my_name} bilan chatga o'tish", url=f"tg://user?id={user_id}")
            
            await bot.send_message(
                target_id,
                f"🎉 **Ajoyib! O'zaro simpatiya (Match)!**\n\n"
                f"Siz layk bosgan **{my_name}** ham sizni yoqtirdi ❤️\n"
                f"Marhamat, bepul bog'laning:",
                reply_markup=back_kb.as_markup(),
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        await message.answer("❤️ Yoqtirildi!")

    await search_profiles(message)

@dp.message(F.text == "👎")
async def process_thumb_dislike(message: types.Message):
    await search_profiles(message)

@dp.message(F.text == "🔙 Orqaga")
async def process_back_text(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_keyboard())

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

async def main():
    await web_server()
    print("Web-server va bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())