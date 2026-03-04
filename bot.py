import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import os
import glob
import requests 
import threading
import re
from flask import Flask

# ==========================================
# 🔒 KEAMANAN TOKEN (Gunakan Secrets Replit!)
# ==========================================
TOKEN = os.environ.get('BOT_TOKEN') 
if not TOKEN:
    # Backup jika belum setting Secrets (Jangan lupa isi Key: BOT_TOKEN di menu Gembok)
    TOKEN = '8622757449:AAGe9pCHqa-PM3SVNZNyJblXzj_h7WLZp60'

bot = telebot.TeleBot(TOKEN)

DOWNLOAD_DIR = 'downloads'
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

user_links = {}
upload_events = {} 

def update_timer(chat_id, msg_id):
    event = upload_events.get(msg_id)
    if not event: return
    seconds = 0
    frames = ["⏳", "⌛"]
    while not event.is_set():
        if event.wait(3.0): break
        seconds += 3
        try:
            teks = f"✅ Media extracted!\n🚀 Uploading to chat... {seconds}s {frames[(seconds//3)%2]}"
            bot.edit_message_text(teks, chat_id=chat_id, message_id=msg_id)
        except: pass

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    teks = (
        "Hello Ozi! 👋 Welcome to *Video Downloader Bot*.\n\n"
        "Kirim link dari TikTok, Instagram, Facebook, X, atau YouTube.\n"
        "Kamu bisa pilih format Video atau MP3!"
    )
    bot.reply_to(message, teks, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    if not url.startswith('http'):
        bot.reply_to(message, "⚠️ Kirim link URL yang valid ya!")
        return

    # Normalisasi link X/Twitter
    url = url.replace('https://x.com/', 'https://twitter.com/').replace('x.com', 'twitter.com')
    user_links[message.chat.id] = url 

    msg = bot.reply_to(message, "⏳ *Fetching media details...*", parse_mode='Markdown')
    
    try:
        # Ambil Info Awal (Judul & Thumbnail)
        ydl_opts_info = {
            'quiet': True, 
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Social Media Media')
            thumb = info.get('thumbnail')

        # Menu Tombol untuk YouTube & TikTok
        if 'youtube.com' in url or 'youtu.be' in url or 'tiktok.com' in url:
            markup = InlineKeyboardMarkup()
            if 'youtube.com' in url or 'youtu.be' in url:
                markup.row(InlineKeyboardButton("🎬 360p (SD)", callback_data="dl|360"), InlineKeyboardButton("🎬 720p (HD)", callback_data="dl|720"))
            else: # Menu Khusus TikTok
                markup.row(InlineKeyboardButton("🎬 Download Video", callback_data="dl|best"))
            
            markup.row(InlineKeyboardButton("🎵 Download Audio (MP3)", callback_data="dl|mp3"))
            
            caption = f"🎥 *{title}*\n\n✅ *Pilih format di bawah ini:* "
            if thumb:
                bot.send_photo(message.chat.id, thumb, caption=caption, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode='Markdown')
            bot.delete_message(message.chat.id, msg.message_id)
        
        else:
            # Langsung proses untuk platform lain (IG/FB/X)
            proses_unduhan(message.chat.id, url, 'best', msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)[:50]}...", chat_id=message.chat.id, message_id=msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl|'))
def handle_query(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    if not url:
        bot.answer_callback_query(call.id, "⚠️ Link kadaluarsa, kirim ulang linknya ya!")
        return
    
    format_choice = call.data.split('|')[1] 
    bot.answer_callback_query(call.id, f"Memproses {format_choice.upper()}...")
    
    # Hapus pesan menu/foto sebelumnya agar rapi
    try: bot.delete_message(chat_id, call.message.message_id)
    except: pass

    msg = bot.send_message(chat_id, f"⏳ *Sedang memproses {format_choice.upper()}...*", parse_mode='Markdown')
    proses_unduhan(chat_id, url, format_choice, msg.message_id)

def proses_unduhan(chat_id, url, format_choice, msg_id):
    # Bersihkan folder downloads
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, '*')):
        try: os.remove(f)
        except: pass

    # Setting Format
    if format_choice == 'mp3':
        fmt = 'bestaudio[ext=m4a]/bestaudio'
    elif format_choice == '360':
        fmt = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]'
    elif format_choice == '720':
        fmt = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]'
    else:
        fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    ydl_opts = {
        'format': fmt,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'), # Nama File Sesuai Judul
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    }

    filename = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Konversi MP3 jika pilihan adalah audio
            if format_choice == 'mp3' and not filename.endswith('.mp3'):
                base = os.path.splitext(filename)[0]
                new_file = base + ".mp3"
                os.rename(filename, new_file)
                filename = new_file

        # Cek ukuran (Limit Telegram 50MB)
        if os.path.getsize(filename) > 49 * 1024 * 1024:
            bot.edit_message_text("⚠️ *File terlalu besar (>50MB).* Telegram tidak mendukung upload file sebesar ini.", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown')
            return

        bot.edit_message_text("✅ Media extracted!\n🚀 Uploading to chat... 0s ⏳", chat_id=chat_id, message_id=msg_id)
        
        upload_events[msg_id] = threading.Event()
        timer_thread = threading.Thread(target=update_timer, args=(chat_id, msg_id))
        timer_thread.start()
        
        judul = info.get('title', 'Social Media Content')
        
        with open(filename, 'rb') as f:
            bot.send_chat_action(chat_id, 'upload_video' if format_choice != 'mp3' else 'upload_audio')
            if format_choice == 'mp3':
                bot.send_audio(chat_id, f, caption=f"🎵 *{judul}*", parse_mode='Markdown')
            else:
                bot.send_video(chat_id, f, caption=f"🎬 *{judul}*", parse_mode='Markdown', supports_streaming=True)

        upload_events[msg_id].set()
        timer_thread.join()
        bot.delete_message(chat_id, msg_id)
        send_donation_message(chat_id)

    except Exception as e:
        if msg_id in upload_events: upload_events[msg_id].set()
        bot.edit_message_text("❌ Gagal mengunduh media. Coba link lain atau tunggu sebentar.", chat_id=chat_id, message_id=msg_id)
    finally:
        if filename and os.path.exists(filename): os.remove(filename)

def send_donation_message(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("☕ Dukung Ozi di Saweria", url="https://saweria.co/oziy77"))
    teks = "✨ *Berhasil diunduh!*\n\nBantu Ozi jaga server tetap nyala dengan donasi seikhlasnya ya! 🙏"
    bot.send_message(chat_id, teks, reply_markup=markup, parse_mode='Markdown')

# Server Flask agar Replit tetap melek
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Ozi is Active!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    print("🤖 Bot is running...")
    bot.infinity_polling()
