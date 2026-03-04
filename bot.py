import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import os
import glob
import requests 
import threading
from flask import Flask

# ==========================================
# 🔒 SISTEM KEAMANAN TOKEN (ANTI-HACK)
# ==========================================
# Kode ini akan mengambil token dari 'Secrets' Replit.
# Jika tidak ditemukan, ia akan menggunakan token manual (hanya untuk lokal).
TOKEN = os.environ.get('BOT_TOKEN') 
if not TOKEN:
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
        if event.wait(3.0): 
            break
        seconds += 3
        try:
            teks_loading = f"✅ Media extracted!\n🚀 Uploading to chat... {seconds}s {frames[(seconds//3)%2]}"
            bot.edit_message_text(teks_loading, chat_id=chat_id, message_id=msg_id)
        except:
            pass

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    teks = (
        "Hello! 👋 Welcome to *Video Downloader Bot*.\n\n"
        "Send me a link from TikTok, Instagram, Facebook, X (Twitter), or YouTube. "
        "For YouTube links, you can choose the video quality or extract the audio to MP3!"
    )
    bot.reply_to(message, teks, disable_web_page_preview=True, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()
    
    if not url.startswith('http'):
        bot.reply_to(message, "⚠️ Please send a valid video URL!")
        return

    url = url.replace('https://x.com/', 'https://twitter.com/').replace('x.com', 'twitter.com')
    if 'youtu.be/' in url: url = url.split('?')[0]
    elif 'youtube.com/watch' in url: url = url.split('&si=')[0]

    if 'youtube.com' in url or 'youtu.be' in url:
        msg = bot.reply_to(message, "⏳ *Fetching media details...*", parse_mode='Markdown')
        try:
            ydl_opts_info = {'quiet': True, 'extractor_args': {'youtube': ['player_client=android,web']}}
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
                thumb_url = info.get('thumbnail')
                title = info.get('title', 'YouTube Video')
            
            user_links[message.chat.id] = url 
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🎬 360p (SD)", callback_data="yt|360"), InlineKeyboardButton("🎬 720p (HD)", callback_data="yt|720"))
            markup.row(InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data="yt|mp3"))
            
            caption = f"🎥 *{title}*\n\n✅ *Select your preferred format below:*"
            if thumb_url:
                bot.send_photo(message.chat.id, thumb_url, caption=caption, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode='Markdown')
            bot.delete_message(message.chat.id, msg.message_id) 
        except Exception as e:
            bot.edit_message_text("❌ Failed to fetch YouTube info.", chat_id=message.chat.id, message_id=msg.message_id)

    elif 'twitter.com' in url or 'x.com' in url:
        msg = bot.reply_to(message, "⏳ *Processing X (Twitter) link...*", parse_mode='Markdown')
        headers = {'User-Agent': 'Mozilla/5.0'}
        bersih_url = url.split('?')[0]
        direct_mp4 = None
        tweet_text = "X (Twitter) Video"

        try:
            api_1 = bersih_url.replace('https://twitter.com/', 'https://api.fxtwitter.com/')
            res1 = requests.get(api_1, headers=headers, timeout=10).json()
            if res1.get('code') == 200:
                videos = res1.get('tweet', {}).get('media', {}).get('videos', [])
                if videos:
                    direct_mp4 = videos[0]['url']
                    tweet_text = res1['tweet'].get('text', tweet_text)
        except: pass

        if not direct_mp4:
            try:
                api_2 = bersih_url.replace('https://twitter.com/', 'https://api.vxtwitter.com/')
                res2 = requests.get(api_2, headers=headers, timeout=10).json()
                if 'media_extended' in res2:
                    for media in res2['media_extended']:
                        if media.get('type') in ['video', 'gif']:
                            direct_mp4 = media['url']
                            tweet_text = res2.get('text', tweet_text)
                            break
            except: pass

        if direct_mp4:
            if len(tweet_text) > 80: tweet_text = tweet_text[:77] + "..."
            vid_path = os.path.join(DOWNLOAD_DIR, f"tw_{message.message_id}.mp4")
            try:
                r = requests.get(direct_mp4, headers=headers, stream=True)
                with open(vid_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk: f.write(chunk)
                
                if os.path.getsize(vid_path) > 48 * 1024 * 1024:
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("🌐 View on Web", url=direct_mp4))
                    pesan_evakuasi = "⚠️ *File is too large (>50MB)*\n👇 *Click below:*"
                    bot.edit_message_text(pesan_evakuasi, chat_id=message.chat.id, message_id=msg.message_id, parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.edit_message_text("✅ Media extracted!\n🚀 Uploading to chat... 0s ⏳", chat_id=message.chat.id, message_id=msg.message_id)
                    upload_events[msg.message_id] = threading.Event()
                    timer_thread = threading.Thread(target=update_timer, args=(message.chat.id, msg.message_id))
                    timer_thread.start()

                    with open(vid_path, 'rb') as video_file:
                        caption = f"🎬 *{tweet_text}*"
                        bot.send_video(message.chat.id, video=video_file, caption=caption, parse_mode='Markdown', supports_streaming=True)
                    
                    upload_events[msg.message_id].set()
                    timer_thread.join()
                    bot.delete_message(message.chat.id, msg.message_id)
                    upload_events.pop(msg.message_id, None)
                    send_donation_message(message.chat.id)
            except Exception as e:
                if msg.message_id in upload_events: upload_events[msg.message_id].set()
                bot.edit_message_text("❌ Failed to process X.", chat_id=message.chat.id, message_id=msg.message_id)
            finally:
                if os.path.exists(vid_path): os.remove(vid_path)
        else:
            bot.edit_message_text("❌ Media not found.", chat_id=message.chat.id, message_id=msg.message_id)

    else:
        msg = bot.reply_to(message, "⏳ *Extracting media...*", parse_mode='Markdown')
        proses_unduhan(message.chat.id, url, 'best', msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('yt|'))
def handle_query(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    if not url:
        bot.answer_callback_query(call.id, "⚠️ Link expired.")
        return
    bot.answer_callback_query(call.id, "Processing...")
    format_choice = call.data.split('|')[1] 
    msg = bot.send_message(chat_id, f"⏳ *Processing {format_choice.upper()}...*", parse_mode='Markdown')
    proses_unduhan(chat_id, url, format_choice, msg.message_id)

# --- UPDATE LINK SAWERIA FIX OZIY77 ---
def send_donation_message(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("☕ Donate on Saweria", url="https://saweria.co/oziy77"))
    donate_text = "✨ *Media downloaded successfully!*\n\nIf you find this bot helpful, support keeping our servers running fast."
    bot.send_message(chat_id, donate_text, reply_markup=markup, parse_mode='Markdown')

def proses_unduhan(chat_id, url, format_choice, msg_id, custom_title=None):
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, '*')):
        try: os.remove(f)
        except: pass

    if format_choice == 'mp3': fmt = 'bestaudio[ext=m4a]/bestaudio'
    elif format_choice == '360': fmt = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best'
    elif format_choice == '720': fmt = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
    else: fmt = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    ydl_opts = {'format': fmt, 'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'), 'quiet': True, 'no_warnings': True, 'extractor_args': {'youtube': ['player_client=android,web']}}
    filename = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            direct_url_fallback = info.get('url', url) 

        if os.path.getsize(filename) > 48 * 1024 * 1024:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🌐 View on Web", url=direct_url_fallback))
            bot.edit_message_text("⚠️ *Too large (>50MB)*", chat_id=chat_id, message_id=msg_id, parse_mode='Markdown', reply_markup=markup)
            return

        bot.edit_message_text("✅ Media extracted!\n🚀 Uploading to chat... 0s ⏳", chat_id=chat_id, message_id=msg_id)
        upload_events[msg_id] = threading.Event()
        timer_thread = threading.Thread(target=update_timer, args=(chat_id, msg_id))
        timer_thread.start()
        
        judul = custom_title if custom_title else info.get('title', 'Social Media Content')
        caption = f"🎬 *{judul}*"
        
        with open(filename, 'rb') as file_data:
            bot.send_chat_action(chat_id, 'upload_video' if format_choice != 'mp3' else 'upload_audio')
            if format_choice == 'mp3':
                bot.send_audio(chat_id=chat_id, audio=file_data, caption=caption, parse_mode='Markdown')
            else:
                bot.send_video(chat_id=chat_id, video=file_data, caption=caption, parse_mode='Markdown', supports_streaming=True)

        upload_events[msg_id].set()
        timer_thread.join()
        bot.delete_message(chat_id=chat_id, message_id=msg_id)
        upload_events.pop(msg_id, None)
        send_donation_message(chat_id)

    except Exception as e:
        if msg_id in upload_events: upload_events[msg_id].set()
        bot.edit_message_text("❌ Failed to fetch media.", chat_id=chat_id, message_id=msg_id)
    finally:
        if filename and os.path.exists(filename): os.remove(filename)

app = Flask(__name__)
@app.route('/')
def keep_alive():
    return "Bot Telegram Ozi is running!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
