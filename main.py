import os
import json
import telebot
from telebot import types
from flask import Flask, request
from dotenv import load_dotenv

# --- Env yuklash ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PORT = int(os.getenv("PORT", 10000))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- JSON yuklash/saqlash ---
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

movies = load_json("movies.json", {})
channels = load_json("channels.json", {"public": [], "private": []})
users = load_json("users.json", {})

waiting_for = {}

# --- Flask route ---
@app.route("/")
def home():
    return "✅ Kino bot ishlayapti (telebot + Flask)"

# --- Webhook endpoint ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# --- Admin panel tugmalari ---
def admin_menu_inline():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎬 Kino qo‘shish", callback_data="add_movie"))
    kb.add(types.InlineKeyboardButton("📂 Kino ro‘yxati", callback_data="list_movies"))
    kb.add(types.InlineKeyboardButton("❌ Kino o‘chirish", callback_data="delete_movie"))
    kb.add(types.InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="add_channel"))
    kb.add(types.InlineKeyboardButton("➖ Kanal o‘chirish", callback_data="remove_channel"))
    kb.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stats"))
    kb.add(types.InlineKeyboardButton("📢 Hammaga xabar", callback_data="broadcast"))
    return kb

# --- /start ---
@bot.message_handler(commands=["start"])
def start(message):
    users[str(message.chat.id)] = True
    save_json("users.json", users)

    if not check_subscription(message.chat.id):
        send_subscribe_message(message.chat.id)
        return

    bot.send_message(message.chat.id, "👋 Salom! Kino raqamini yuboring va men sizga yuboraman.")

# --- /admin ---
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
    elif call.data == "delete_movie":
        bot.send_message(call.message.chat.id, "❌ O‘chiriladigan kino raqamini yuboring:")
        waiting_for[call.message.chat.id] = "delete_movie"
    elif call.data == "add_channel":
        bot.send_message(call.message.chat.id, "➕ Kanal username yoki ID yuboring:")
        waiting_for[call.message.chat.id] = "add_channel"
    elif call.data == "remove_channel":
        bot.send_message(call.message.chat.id, "➖ O‘chiriladigan kanalni yuboring:")
        waiting_for[call.message.chat.id] = "remove_channel"
    elif call.data == "stats":
        text = f"📊 Foydalanuvchilar: {len(users)}\n🎬 Kinolar: {len(movies)}\n📢 Kanallar: {len(channels.get('public', [])) + len(channels.get('private', []))}"
        bot.send_message(call.message.chat.id, text)
    elif call.data == "broadcast":
        bot.send_message(call.message.chat.id, "📢 Hammaga yuboriladigan xabarni yozing:")
        waiting_for[call.message.chat.id] = "broadcast"

# --- Kino va boshqa xabarlar ---
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
            save_json("movies.json", movies)
            bot.send_message(user_id, f"✅ Kino qo‘shildi!\nRaqam: {number}\nNomi: {title}")
            del waiting_for[user_id]
            return
        elif step == "delete_movie":
            number = message.text
            if number in movies:
                del movies[number]
                save_json("movies.json", movies)
                bot.send_message(user_id, f"🗑 Kino o‘chirildi: {number}")
            else:
                bot.send_message(user_id, "❌ Kino topilmadi")
            del waiting_for[user_id]
            return
        elif step == "add_channel":
            ch = message.text
            if ch.startswith("-100"):
                channels.setdefault("private", []).append(ch)
            else:
                channels.setdefault("public", []).append(ch)
            save_json("channels.json", channels)
            bot.send_message(user_id, f"✅ Kanal qo‘shildi: {ch}")
            del waiting_for[user_id]
            return
        elif step == "remove_channel":
            ch = message.text
            if ch in channels.get("private", []):
                channels["private"].remove(ch)
            elif ch in channels.get("public", []):
                channels["public"].remove(ch)
            else:
                bot.send_message(user_id, "❌ Kanal topilmadi")
            save_json("channels.json", channels)
            bot.send_message(user_id, f"🗑 O‘chirildi: {ch}")
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
    for ch in channels.get("public", []):
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

def send_subscribe_message(user_id):
    kb = types.InlineKeyboardMarkup()
    for i, ch in enumerate(channels.get("public", []), 1):
        kb.add(types.InlineKeyboardButton(f"Kanal {i}", url=f"https://t.me/{ch.replace('@','')}"))
    bot.send_message(user_id, "❗️ Botdan foydalanish uchun kanallarga obuna bo‘ling", reply_markup=kb)

# --- Hammaga xabar ---
def send_broadcast(text):
    for uid in users.keys():
        try:
            bot.send_message(int(uid), text)
        except:
            pass

# --- Flask run ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
