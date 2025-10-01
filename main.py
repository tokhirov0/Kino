import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramForbiddenError
import os

API_TOKEN = os.getenv("BOT_TOKEN")  # Render .env ichida saqlanadi
ADMIN_ID = 6733100026  # Admin ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Ma'lumotlar ---
movies = {}          # {raqam: {"name": nomi, "file_id": video_id}}
channels = []        # ["@kanal1", "-1001234567890", ...]
users = set()        # foydalanuvchilar ID-lari

# --- Majburiy obuna tekshirish ---
async def check_subscription(user_id):
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

def channel_buttons():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Kanal{i+1}", url=f"https://t.me/{ch.replace('@','')}" if ch.startswith("@") else "https://t.me/")]
        for i, ch in enumerate(channels)
    ])
    return kb

# --- Oddiy foydalanuvchilar uchun start ---
@dp.message(Command("start"))
async def start(message: types.Message):
    users.add(message.from_user.id)

    if not await check_subscription(message.from_user.id):
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo‘ling:", reply_markup=channel_buttons())
        return

    if message.from_user.id == ADMIN_ID:
        await show_admin_panel(message.chat.id)
    else:
        await message.answer("🎬 Kino botga xush kelibsiz!\nFilm kodini yuboring:")

# --- Kino izlash ---
@dp.message(lambda m: m.text and m.text.isdigit())
async def get_movie(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo‘ling:", reply_markup=channel_buttons())
        return

    movie_id = int(message.text)
    if movie_id in movies:
        data = movies[movie_id]
        await message.answer_video(data["file_id"], caption=f"{data['name']} (ID: {movie_id})")
    else:
        await message.answer("❌ Bunday ID bo‘yicha film topilmadi.")

# ================= ADMIN PANEL =================
def admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🎬 Kino qo‘shish"))
    kb.add(KeyboardButton("📂 Kino ro‘yxati"))
    kb.add(KeyboardButton("➕ Kanal qo‘shish"), KeyboardButton("➖ Kanal o‘chirish"))
    kb.add(KeyboardButton("📢 Hammaga xabar"))
    return kb

async def show_admin_panel(chat_id):
    await bot.send_message(chat_id, "👮 Admin panel:", reply_markup=admin_keyboard())

# --- Admin tugmalari ---
@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "🎬 Kino qo‘shish")
async def admin_add_movie(message: types.Message):
    await message.answer("🎥 Kino videosini yuboring:")

@dp.message(lambda m: m.from_user.id == ADMIN_ID, content_types=["video"])
async def add_movie(message: types.Message):
    await message.answer("📌 Kino raqamini yuboring:")
    dp.message.register(get_movie_id, temp_video=message.video.file_id)

async def get_movie_id(message: types.Message, temp_video):
    if not message.text.isdigit():
        await message.answer("❌ Raqam yozing.")
        return
    movie_id = int(message.text)
    await message.answer("🎬 Kino nomini yuboring:")
    dp.message.register(get_movie_name, movie_id=movie_id, video_id=temp_video)

async def get_movie_name(message: types.Message, movie_id, video_id):
    movie_name = message.text
    movies[movie_id] = {"name": movie_name, "file_id": video_id}
    await message.answer(f"✅ Kino qo‘shildi:\nID: {movie_id}\nNomi: {movie_name}")

# --- Kino ro‘yxati ---
@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "📂 Kino ro‘yxati")
async def movie_list(message: types.Message):
    if not movies:
        await message.answer("📭 Hali kino qo‘shilmagan.")
    else:
        text = "🎞 Kinolar ro‘yxati:\n\n"
        for mid, data in movies.items():
            text += f"ID: {mid} | {data['name']}\n"
        await message.answer(text)

# --- Kanal qo‘shish ---
@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "➕ Kanal qo‘shish")
async def add_channel_request(message: types.Message):
    await message.answer("➕ Kanal username yoki ID yuboring:")

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text.startswith("@") or m.text.startswith("-100"))
async def add_channel(message: types.Message):
    channel = message.text.strip()
    if channel not in channels:
        channels.append(channel)
        await message.answer(f"✅ Kanal qo‘shildi: {channel}")
    else:
        await message.answer("❌ Bu kanal allaqachon mavjud.")

# --- Kanal o‘chirish ---
@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "➖ Kanal o‘chirish")
async def del_channel_request(message: types.Message):
    if not channels:
        await message.answer("❌ Hali kanal qo‘shilmagan.")
        return
    text = "🗑 Qaysi kanalni o‘chirmoqchisiz?\n\n" + "\n".join(channels)
    await message.answer(text)

@dp.message(lambda m: m.from_user.id == ADMIN_ID and (m.text in channels))
async def del_channel(message: types.Message):
    channel = message.text.strip()
    if channel in channels:
        channels.remove(channel)
        await message.answer(f"🗑 Kanal o‘chirildi: {channel}")
    else:
        await message.answer("❌ Kanal topilmadi.")

# --- Hammaga xabar yuborish ---
@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text == "📢 Hammaga xabar")
async def broadcast_request(message: types.Message):
    await message.answer("📨 Yuboriladigan xabarni kiriting:")

@dp.message(lambda m: m.from_user.id == ADMIN_ID and m.text not in ["🎬 Kino qo‘shish","📂 Kino ro‘yxati","➕ Kanal qo‘shish","➖ Kanal o‘chirish","📢 Hammaga xabar"])
async def broadcast_message(message: types.Message):
    text = message.text
    count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            count += 1
        except TelegramForbiddenError:
            pass
    await message.answer(f"✅ Xabar {count} ta foydalanuvchiga yuborildi.")

# --- Run ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
