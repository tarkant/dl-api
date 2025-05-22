import os
import re
import requests
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# Configuration
API_KEY = os.environ.get("API_KEY")  # The same API key as your FastAPI app
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")  # Change to your FastAPI base URL
LOG_VERBOSE = os.environ.get("LOG_VERBOSE", "1") == "1"

# Regex to detect URLs (simple version)
URL_REGEX = re.compile(r"https?://\S+")

# Allowed group IDs from environment variable (comma-separated or JSON list)
ALLOWED_GROUP_IDS_ENV = os.environ.get("ALLOWED_GROUP_IDS", "")
if ALLOWED_GROUP_IDS_ENV.strip().startswith("["):
    ALLOWED_GROUP_IDS = set(int(gid) for gid in json.loads(ALLOWED_GROUP_IDS_ENV))
else:
    ALLOWED_GROUP_IDS = set(int(gid) for gid in ALLOWED_GROUP_IDS_ENV.split(",") if gid.strip())

# Allowed base URLs from environment variable (comma-separated or JSON list)
ALLOWED_URLS_ENV = os.environ.get("ALLOWED_URL_WHITELIST", "")
if ALLOWED_URLS_ENV.strip().startswith("["):
    ALLOWED_URL_WHITELIST = set(json.loads(ALLOWED_URLS_ENV))
else:
    ALLOWED_URL_WHITELIST = set(u.strip() for u in ALLOWED_URLS_ENV.split(",") if u.strip())

def is_url_allowed(url: str) -> bool:
    for allowed in ALLOWED_URL_WHITELIST:
        if url.startswith(allowed):
            return True
    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        if LOG_VERBOSE:
            print("[BOT] No message or text found in update.")
        return
    chat_id = update.effective_chat.id
    if LOG_VERBOSE:
        print(f"[BOT] Received message in chat_id: {chat_id}")
    if chat_id not in ALLOWED_GROUP_IDS:
        if LOG_VERBOSE:
            print(f"[BOT] Message from unauthorized chat_id: {chat_id}. ALLOWED_GROUP_IDS: {ALLOWED_GROUP_IDS}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ This bot is not authorized to operate in this group. Your group id: {chat_id}")
        return
    if LOG_VERBOSE:
        print(f"[BOT] Received message: {update.message.text}")
    urls = URL_REGEX.findall(update.message.text)
    if LOG_VERBOSE:
        print(f"[BOT] URLs found: {urls}")
    valid_urls = [url for url in urls if is_url_allowed(url)]
    if not valid_urls:
        if LOG_VERBOSE:
            print("[BOT] No valid URLs found in message.")
        return
    for url in valid_urls:
        print(f"[BOT] Detected and allowed URL: {url}")
        # Send a single status message and update it as the process goes
        status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔗 URL received!\nProcessing: {url}\nStarting download...")
        print(f"[BOT] Sent status message for {url}, message_id: {status_msg.message_id}")
        try:
            await status_msg.edit_text(f"⏳ Downloading video for: {url}")
            print(f"[BOT] Status message edited to downloading for {url}")
            params = {"url": url, "output_format": "mp4"}
            headers = {"x-api-key": API_KEY}
            api_url = f"{API_BASE_URL}/download_and_cleanup/"
            print(f"[BOT] Sending POST to {api_url} with params {params}")
            resp = requests.post(api_url, params=params, headers=headers, stream=True)
            print(f"[BOT] API response status: {resp.status_code}")
            if resp.status_code == 200:
                filename = url.split("/")[-1].split("?")[0] or "video.mp4"
                print(f"[BOT] Saving file as: {filename}")
                with open(filename, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"[BOT] Downloaded file: {filename}")
                await status_msg.edit_text(f"✅ Download complete! Sending file for: {url}")
                print(f"[BOT] Status message edited to download complete for {url}")
                with open(filename, "rb") as video_file:
                    await context.bot.send_video(chat_id=update.effective_chat.id, video=video_file, caption=f"Here is your video for: {url}")
                    print(f"[BOT] Video sent for {url}")
                await status_msg.edit_text(f"✅ Video sent for: {url}")
                print(f"[BOT] Status message edited to video sent for {url}")
                os.remove(filename)
                print(f"[BOT] File sent and removed: {filename}")
            else:
                print(f"[BOT] Failed to download: {resp.text}")
                await status_msg.edit_text(f"❌ Could not download the file for: {url}\nReason: {resp.text}")
        except Exception as e:
            print(f"[BOT] Exception: {e}")
            try:
                await status_msg.edit_text(f"❌ Error processing {url}: {e}")
            except Exception as edit_exc:
                print(f"[BOT] Could not edit status message: {edit_exc}")

if __name__ == "__main__":
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        print("Please set the TELEGRAM_TOKEN environment variable.")
        exit(1)
    if not API_KEY:
        print("Please set the API_KEY environment variable (same as your FastAPI app).")
        exit(1)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot is running...")
    app.run_polling()
