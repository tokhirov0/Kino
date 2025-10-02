import os
import json
from flask import Flask, request
import telebot
from dotenv import load_dotenv

# .env yuklash
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Fayllar
USERS_FILE = "users.json"
MOVIES_FILE = "movies.json"
CHANNELS_FILE = "channels.json"

# Fayllarni yaratib qo‘yish
for file in [USERS_FILE, MOVIES_FILE, CHANNELS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([] if file != MOVIES_FILE else {}, f)

# JSON o‘qish/yozish
def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Majburiy kanallarni tekshirish
def check_subscribe(user_id):
    channels = load_json(CHANNELS_FILE)
    for ch in channels:
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            # "pending" - so'rovda turganlar uchun ham ruxsat beramiz
            if status not in ["member", "administrator", "creator", "pending"]:
                return False
        except Exception as e:
            return False
    return True

# /start komandasi
@bot.message_handler(commands=["start"])
def start(message):
    users = load_json(USERS_FILE)
    if message.chat.id not in users:
        users.append(message.chat.id)
        save_json(USERS_FILE, users)

    if not check_subscribe(message.chat.id):
        channels = load_json(CHANNELS_FILE)
        text = "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:\n\n"
        markup = telebot.types.InlineKeyboardMarkup()
        for i, ch in enumerate(channels, start=1):
            markup.add(telebot.types.InlineKeyboardButton(
                f"{i}-kanal", url=ch["link"]))
        markup.add(telebot.types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))
        bot.send_message(message.chat.id, text, reply_markup=markup)
        return

    bot.send_message(message.chat.id, "🎬 Xush kelibsiz! Kino raqamini yuboring.")

# Tekshirish tugmasi
@bot.callback_query_handler(func=lambda call: call.data == "check")
def callback_check(call):
    if check_subscribe(call.from_user.id):
        bot.send_message(call.from_user.id, "✅ Obuna tekshirildi! Endi kino raqamini yuboring.")
    else:
        bot.send_message(call.from_user.id, "❌ Avval barcha kanallarga obuna bo‘ling.")

# Kino raqam yuborganda
@bot.message_handler(func=lambda m: m.text.isdigit())
def get_movie(message):
    movies = load_json(MOVIES_FILE)
    movie_id = message.text
    if movie_id in movies:
        data = movies[movie_id]
        bot.send_message(message.chat.id, f"🎬 {data['name']}")
        bot.send_video(message.chat.id, data["file_id"])
    else:
        bot.send_message(message.chat.id, "❌ Bunday kino topilmadi.")

# ===== ADMIN PANEL =====
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.chat.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ Kino qo‘shish", "❌ Kino o‘chirish")
        markup.add("📢 Hammaga xabar", "📊 Statistika")
        markup.add("➕ Kanal qo‘shish", "❌ Kanal o‘chirish")
        bot.send_message(message.chat.id, "⚙️ Admin panel:", reply_markup=markup)

# Kino qo‘shish
@bot.message_handler(func=lambda m: m.text == "➕ Kino qo‘shish" and m.chat.id == ADMIN_ID)
def ask_movie(message):
    msg = bot.reply_to(message, "🎥 Kino videosini yuboring:")
    bot.register_next_step_handler(msg, process_movie)

def process_movie(message):
    if message.video:
        file_id = message.video.file_id
        msg = bot.reply_to(message, "🎬 Kino nomini yuboring:")
        bot.register_next_step_handler(msg, save_movie, file_id)
    else:
        bot.reply_to(message, "❌ Faqat video yuboring!")

def save_movie(message, file_id):
    movies = load_json(MOVIES_FILE)
    new_id = str(len(movies) + 1)
    movies[new_id] = {"name": message.text, "file_id": file_id}
    save_json(MOVIES_FILE, movies)

    users = load_json(USERS_FILE)
    for uid in users:
        try:
            bot.send_message(uid, f"📢 Yangi kino qo‘shildi!\n\n🎬 {message.text}\nID: {new_id}")
        except Exception as e:
            pass

    bot.send_message(message.chat.id, f"✅ Kino qo‘shildi!\nID: {new_id}")

# Kino o‘chirish
@bot.message_handler(func=lambda m: m.text == "❌ Kino o‘chirish" and m.chat.id == ADMIN_ID)
def delete_movie(message):
    msg = bot.reply_to(message, "🗑 O‘chirmoqchi bo‘lgan kino ID raqamini yuboring:")
    bot.register_next_step_handler(msg, confirm_delete)

def confirm_delete(message):
    movies = load_json(MOVIES_FILE)
    if message.text in movies:
        del movies[message.text]
        save_json(MOVIES_FILE, movies)
        bot.send_message(message.chat.id, "✅ Kino o‘chirildi.")
    else:
        bot.send_message(message.chat.id, "❌ Bunday ID topilmadi.")

# Hammaga xabar
@bot.message_handler(func=lambda m: m.text == "📢 Hammaga xabar" and m.chat.id == ADMIN_ID)
def ask_broadcast(message):
    msg = bot.reply_to(message, "✍️ Xabar matnini yuboring:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(message):
    users = load_json(USERS_FILE)
    for uid in users:
        try:
            bot.send_message(uid, f"📢 {message.text}")
        except:
            pass
    bot.send_message(message.chat.id, "✅ Hammaga yuborildi.")

# Statistika
@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.chat.id == ADMIN_ID)
def stats(message):
    users = load_json(USERS_FILE)
    movies = load_json(MOVIES_FILE)
    bot.send_message(message.chat.id, f"👥 Foydalanuvchilar: {len(users)}\n🎬 Kinolar: {len(movies)}")

# --- Kanal qo‘shish ---
@bot.message_handler(func=lambda m: m.text == "➕ Kanal qo‘shish" and m.chat.id == ADMIN_ID)
def ask_channel(message):
    msg = bot.reply_to(message, "Kanal ID (-100...) va invite-linkni vergul bilan yuboring:\nMasalan: -1001234567890, https://t.me/+invitecode")
    bot.register_next_step_handler(msg, save_channel)

def save_channel(message):
    channels = load_json(CHANNELS_FILE)
    try:
        ch_id, ch_link = message.text.split(",")
        ch_id = ch_id.strip()
        ch_link = ch_link.strip()
        channels.append({"id": ch_id, "link": ch_link})
        save_json(CHANNELS_FILE, channels)
        bot.send_message(message.chat.id, "✅ Kanal qo‘shildi.")
    except:
        bot.send_message(message.chat.id, "❌ Format xato. Masalan: -1001234567890, https://t.me/+invitecode")

# --- Kanal o‘chirish ---
@bot.message_handler(func=lambda m: m.text == "❌ Kanal o‘chirish" and m.chat.id == ADMIN_ID)
def delete_channel(message):
    channels = load_json(CHANNELS_FILE)
    s = ""
    for i, ch in enumerate(channels, start=1):
        s += f"{i}. {ch['id']} - {ch['link']}\n"
    msg = bot.reply_to(message, f"🗑 O‘chirmoqchi bo‘lgan kanal raqamini yuboring (1,2,3 ...):\n{s}")
    bot.register_next_step_handler(msg, confirm_delete_channel)

def confirm_delete_channel(message):
    channels = load_json(CHANNELS_FILE)
    try:
        idx = int(message.text) - 1
        if 0 <= idx < len(channels):
            deleted = channels.pop(idx)
            save_json(CHANNELS_FILE, channels)
            bot.send_message(message.chat.id, f"✅ Kanal o‘chirildi: {deleted['link']}")
        else:
            bot.send_message(message.chat.id, "❌ Noto‘g‘ri raqam.")
    except:
        bot.send_message(message.chat.id, "❌ Xato format.")

# Flask webhook
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_update = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_update)
    bot.process_new_updates([update])
    return "ok", 200

@app.route("/")
def index():
    return "Bot ishlayapti ✅"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
