import os
import json
from flask import Flask, request
import telebot
from telebot import types
from dotenv import load_dotenv

# --- Env yuklash ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- JSON load/save ---
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

# --- Invite link caching ---
def get_invite_link(ch_id):
    try:
        links = load_json("invite_links.json", {})
        if ch_id in links:
            return links[ch_id]
        invite = bot.create_chat_invite_link(ch_id)
        links[ch_id] = invite.invite_link
        save_json("invite_links.json", links)
        print(f"[INFO] Invite link yaratildi: {ch_id}")
        return invite.invite_link
    except Exception as e:
        print(f"[ERROR] Invite yaratishda xato: {e}")
        return "https://t.me/your_public_channel"

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

# --- Check subscription ---
def check_subscription(user_id):
    if not channels:
        return True
    for ch in channels:
        ch_id = ch["id"] if isinstance(ch, dict) else ch
        ch_type = ch.get("type") if isinstance(ch, dict) else "public"
        try:
            if ch_type == "private":
                member = bot.get_chat_member(ch_id, user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    return False
            else:
                member = bot.get_chat_member(ch_id, user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    return False
        except:
            return False
    return True

# --- Send subscribe message ---
def send_subscribe_message(user_id):
    kb = types.InlineKeyboardMarkup()
    for i, ch in enumerate(channels, 1):
        ch_id = ch["id"] if isinstance(ch, dict) else ch
        ch_type = ch.get("type") if isinstance(ch, dict) else "public"
        if ch_type == "private":
            url = get_invite_link(ch_id)
        else:
            url = f"https://t.me/{ch_id.replace('@','')}"
        kb.add(types.InlineKeyboardButton(f"Kanal{i}", url=url))
    bot.send_message(user_id, "❗️ Botdan foydalanish uchun kanallarga obuna bo‘ling", reply_markup=kb)

# --- Broadcast ---
def send_broadcast(text):
    for uid in users.keys():
        try:
            bot.send_message(int(uid), text)
        except:
            pass

# --- Handlers ---
@bot.message_handler(commands=["start"])
def start(message):
    users[str(message.chat.id)] = True
    save_json("users.json", users)
    if not check_subscription(message.chat.id):
        send_subscribe_message(message.chat.id)
        return
    bot.send_message(message.chat.id, "👋 Salom! Kino raqamini yuboring va men sizga yuboraman.")

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, "🔐 Admin panel:", reply_markup=admin_menu_inline())

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

@bot.message_handler(content_types=["text", "video"])
def handle_message(message):
    user_id = message.chat.id
    # Admin workflow
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
            channels.append({"id": message.text, "type": "public"})
            save_json("channels.json", channels)
            bot.send_message(user_id, f"✅ Kanal qo‘shildi: {message.text}")
            del waiting_for[user_id]
            return
        elif step == "remove_channel":
            found = False
            for ch in channels:
                ch_id = ch["id"] if isinstance(ch, dict) else ch
                if ch_id == message.text:
                    channels.remove(ch)
                    save_json("channels.json", channels)
                    bot.send_message(user_id, f"🗑 O‘chirildi: {message.text}")
                    found = True
                    break
            if not found:
                bot.send_message(user_id, "❌ Kanal topilmadi")
            del waiting_for[user_id]
            return
        elif step == "broadcast":
            send_broadcast(message.text)
            del waiting_for[user_id]
            return

    # User kino request
    if message.text.isdigit():
        number = message.text
        if number in movies:
            data = movies[number]
            bot.send_video(user_id, data["file_id"], caption=f"{number}. {data['title']}")
        else:
            bot.send_message(user_id, "❌ Bunday kino topilmadi.")

# --- Flask webhook endpoint ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def home():
    return "✅ Kino bot ishlayapti!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
