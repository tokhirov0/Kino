import telebot
from telebot import types
from flask import Flask
import threading

# --- Sozlamalar ---
BOT_TOKEN = "BOT_TOKENINGNI_BU_YERGA_QO'Y"
ADMIN_ID = 6733100026  # o'zingizning Telegram ID

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Ma'lumotlar (oddiy dictionary) ---
movies = {}
channels = []
waiting_for = {}

# --- Flask route (browser uchun) ---
@app.route("/")
def home():
    return "✅ Kino bot ishlayapti!"

# --- Admin panel tugmalari ---
def admin_menu_inline():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🎬 Kino qo‘shish", callback_data="add_movie"),
        types.InlineKeyboardButton("📂 Kino ro‘yxati", callback_data="list_movies")
    )
    kb.add(
        types.InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="add_channel"),
        types.InlineKeyboardButton("➖ Kanal o‘chirish", callback_data="remove_channel")
    )
    kb.add(
        types.InlineKeyboardButton("📢 Hammaga xabar", callback_data="broadcast")
    )
    return kb

# --- Start ---
@bot.message_handler(commands=["start"])
def start(message):
    if not check_subscription(message.chat.id):
        send_subscribe_message(message.chat.id)
        return
    bot.send_message(message.chat.id, "👋 Salom! Kino raqamini yuboring va men sizga yuboraman.")

# --- Admin panel ---
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, "🔐 Admin panel:", reply_markup=admin_menu_inline())

# --- Callback handler ---
@bot.callback_query_handler(func=lambda call: True)
def admin_callbacks(call):
    if call.message.chat.id != ADMIN_ID:
        return
    if call.data == "add_movie":
        bot.send_message(call.message.chat.id, "🎬 Kino raqamini yuboring:")
        waiting_for[call.message.chat.id] = "movie_number"
    elif call.data == "list_movies":
        if movies:
            text = "📂 Kino ro‘yxati:\n\n"
            for num, data in movies.items():
                text += f"{num}. {data['title']}\n"
        else:
            text = "❌ Hali kino qo‘shilmagan."
        bot.send_message(call.message.chat.id, text)
    elif call.data == "add_channel":
        bot.send_message(call.message.chat.id, "➕ Kanal username yoki ID yuboring:")
        waiting_for[call.message.chat.id] = "add_channel"
    elif call.data == "remove_channel":
        bot.send_message(call.message.chat.id, "➖ O‘chiriladigan kanal username yoki ID yuboring:")
        waiting_for[call.message.chat.id] = "remove_channel"
    elif call.data == "broadcast":
        bot.send_message(call.message.chat.id, "📢 Hammaga yuboriladigan xabarni yozing:")
        waiting_for[call.message.chat.id] = "broadcast"

# --- Xabarlar ---
@bot.message_handler(content_types=["text", "video"])
def handle_message(message):
    user_id = message.chat.id

    if user_id == ADMIN_ID and user_id in waiting_for:
        step = waiting_for[user_id]
        if step == "movie_number":
            waiting_for[user_id] = {"step": "movie_title", "number": message.text}
            bot.send_message(user_id, "🎬 Kino nomini yuboring:")
            return
        elif isinstance(step, dict) and step.get("step") == "movie_title":
            number = step["number"]
            title = message.text
            waiting_for[user_id] = {"step": "movie_file", "number": number, "title": title}
            bot.send_message(user_id, "📹 Endi kinoni yuboring:")
            return
        elif isinstance(step, dict) and step.get("step") == "movie_file" and message.content_type == "video":
            number = step["number"]
            title = step["title"]
            file_id = message.video.file_id
            movies[number] = {"title": title, "file_id": file_id}
            bot.send_message(user_id, f"✅ Kino qo‘shildi!\nRaqam: {number}\nNomi: {title}")
            del waiting_for[user_id]
            return
        elif step == "add_channel":
            channels.append(message.text)
            bot.send_message(user_id, f"✅ Kanal qo‘shildi: {message.text}")
            del waiting_for[user_id]
            return
        elif step == "remove_channel":
            if message.text in channels:
                channels.remove(message.text)
                bot.send_message(user_id, f"🗑 O‘chirildi: {message.text}")
            else:
                bot.send_message(user_id, "❌ Kanal topilmadi")
            del waiting_for[user_id]
            return
        elif step == "broadcast":
            send_broadcast(message.text)
            del waiting_for[user_id]
            return

    if message.text.isdigit():
        number = message.text
        if number in movies:
            data = movies[number]
            bot.send_video(user_id, data["file_id"], caption=f"{number}. {data['title']}")
        else:
            bot.send_message(user_id, "❌ Bunday kino topilmadi.")

# --- Kanal tekshirish ---
def check_subscription(user_id):
    if not channels:
        return True
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ["member", "administrator", "creator"]:
                continue
            else:
                return False
        except:
            return False
    return True

def send_subscribe_message(user_id):
    kb = types.InlineKeyboardMarkup()
    for i, ch in enumerate(channels, 1):
        kb.add(types.InlineKeyboardButton(f"Kanal{i}", url=f"https://t.me/{ch.replace('@','')}"))
    bot.send_message(user_id, "❗️ Botdan foydalanish uchun kanallarga obuna bo‘ling", reply_markup=kb)

# --- Hammaga xabar ---
def send_broadcast(text):
    for uid in movies.keys():  # bu yerda alohida userlar bazasini saqlash kerak
        try:
            bot.send_message(uid, text)
        except:
            pass

# --- Botni fon rejimida ishga tushirish ---
def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=5000)
