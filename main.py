import os
import json
import threading
import telebot
from telebot import types
from flask import Flask
from dotenv import load_dotenv

# --- Env yuklash ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

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
channels = load_json("channels.json", [])
users = load_json("users.json", {})

waiting_for = {}

# --- Flask route ---
@app.route("/")
def home():
    return "✅ Kino bot ishlayapti (telebot + Flask)"

# --- Admin panel ---
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
    users[str(message.chat.id)] = True
    save_json("users.json", users)

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
        bot.send_message(call.message.chat.id, "➕ Kanal username yoki ID yuboring (private/public format):")
        waiting_for[call.message.chat.id] = "add_channel"
    elif call.data == "remove_channel":
        bot.send_message(call.message.chat.id, "➖ O‘chiriladigan kanal username yoki ID yuboring:")
        waiting_for[call.message.chat.id] = "remove_channel"
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
        elif step == "add_channel":
            # private/public ajratish uchun JSON format kiritamiz
            try:
                parts = message.text.split("|")
                ch_id = parts[0].strip()
                ch_type = parts[1].strip().lower() if len(parts) > 1 else "public"
                channels.append({"id": ch_id, "type": ch_type})
                save_json("channels.json", channels)
                bot.send_message(user_id, f"✅ Kanal qo‘shildi: {ch_id} ({ch_type})")
            except:
                bot.send_message(user_id, "❌ Format xato. Masalan: -100123456789|private yoki @kanalusername|public")
            del waiting_for[user_id]
            return
        elif step == "remove_channel":
            ch_id = message.text.strip()
            removed = False
            for ch in channels:
                if ch.get("id") == ch_id:
                    channels.remove(ch)
                    removed = True
                    break
            if removed:
                save_json("channels.json", channels)
                bot.send_message(user_id, f"🗑 O‘chirildi: {ch_id}")
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
        ch_id = ch["id"] if isinstance(ch, dict) else ch
        try:
            member = bot.get_chat_member(ch_id, user_id)
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
        ch_id = ch["id"] if isinstance(ch, dict) else ch
        ch_type = ch.get("type") if isinstance(ch, dict) else "public"

        if ch_type == "private":
            try:
                invite = bot.create_chat_invite_link(ch_id)
                kb.add(types.InlineKeyboardButton(f"Kanal{i}", url=invite.invite_link))
            except Exception as e:
                print("Invite yaratishda xato:", e)
                kb.add(types.InlineKeyboardButton(f"Kanal{i}", url="https://t.me/your_public_channel"))
        else:
            kb.add(types.InlineKeyboardButton(f"Kanal{i}", url=f"https://t.me/{ch_id.replace('@','')}"))

    bot.send_message(user_id, "❗️ Botdan foydalanish uchun kanallarga obuna bo‘ling", reply_markup=kb)

# --- Hammaga xabar ---
def send_broadcast(text):
    for uid in users.keys():
        try:
            bot.send_message(int(uid), text)
        except:
            pass

# --- Botni ishga tushirish ---
def run_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
