import os
import re
import hmac
import base64
import hashlib
import tempfile
import asyncio
import subprocess
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)
import yt_dlp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ACR_HOST = os.getenv("ACR_HOST", "").strip()
ACR_ACCESS_KEY = os.getenv("ACR_ACCESS_KEY", "").strip()
ACR_ACCESS_SECRET = os.getenv("ACR_ACCESS_SECRET", "").strip()
MAX_DOWNLOAD_MB = int(os.getenv("MAX_DOWNLOAD_MB", "45"))
MAX_DURATION = int(os.getenv("MAX_DURATION_SECONDS", "900"))

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
ALLOWED_HOSTS = {
    "instagram.com", "www.instagram.com", "m.instagram.com",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"
}

def valid_social_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host in ALLOWED_HOSTS
    except Exception:
        return False

def extract_audio(source: Path, target: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(source), "-vn",
        "-ac", "1", "-ar", "44100", "-b:a", "128k", str(target)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def acr_identify(audio_path: Path) -> dict:
    if not (ACR_HOST and ACR_ACCESS_KEY and ACR_ACCESS_SECRET):
        raise RuntimeError("تنظیمات ACRCloud در فایل .env کامل نشده است.")
    endpoint = "/v1/identify"
    http_method = "POST"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(datetime.now().timestamp()))
    string_to_sign = (
        f"{http_method}\n{endpoint}\n{ACR_ACCESS_KEY}\n"
        f"{data_type}\n{signature_version}\n{timestamp}"
    )
    digest = hmac.new(
        ACR_ACCESS_SECRET.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha1
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    url = f"https://{ACR_HOST}{endpoint}"
    with audio_path.open("rb") as sample:
        response = requests.post(
            url,
            files={"sample": sample},
            data={
                "access_key": ACR_ACCESS_KEY,
                "sample_bytes": str(audio_path.stat().st_size),
                "timestamp": timestamp,
                "signature": signature,
                "data_type": data_type,
                "signature_version": signature_version,
            },
            timeout=45,
        )
    response.raise_for_status()
    return response.json()

def format_recognition(result: dict) -> str:
    status = result.get("status", {})
    if status.get("code") != 0:
        return "نتونستم آهنگ رو تشخیص بدم. ممکنه صدا کوتاه، بی‌کیفیت یا دارای نویز زیاد باشه."
    music = result.get("metadata", {}).get("music", [])
    if not music:
        return "آهنگی در فایل پیدا نشد."
    item = music[0]
    title = item.get("title", "نامشخص")
    artists = ", ".join(a.get("name", "") for a in item.get("artists", [])) or "نامشخص"
    album = item.get("album", {}).get("name", "")
    lines = [f"🎵 آهنگ: {title}", f"🎤 خواننده: {artists}"]
    if album:
        lines.append(f"💿 آلبوم: {album}")
    return "\n".join(lines)

def download_public_media(url: str, folder: Path) -> Path:
    if not valid_social_url(url):
        raise ValueError("فقط لینک عمومی اینستاگرام یا تیک‌تاک پذیرفته می‌شه.")
    output = str(folder / "media.%(ext)s")
    options = {
        "outtmpl": output,
        "format": "best[filesize<={}] / best".format(MAX_DOWNLOAD_MB * 1024 * 1024),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "restrictfilenames": True,
        "socket_timeout": 25,
        "retries": 2,
        "max_filesize": MAX_DOWNLOAD_MB * 1024 * 1024,
       
  
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])
    files = [p for p in folder.glob("media.*") if p.is_file()]
    if not files:
        raise RuntimeError("فایل دانلود نشد؛ ممکنه لینک خصوصی، حذف‌شده یا محدود باشه.")
    file_path = files[0]
    if file_path.stat().st_size > MAX_DOWNLOAD_MB * 1024 * 1024:
        file_path.unlink(missing_ok=True)
        raise RuntimeError(f"حجم فایل بیشتر از سقف {MAX_DOWNLOAD_MB} مگابایت است.")
    return file_path

async def send_media(update: Update, path: Path, caption: str = "") -> None:
    size = path.stat().st_size
    if size > MAX_DOWNLOAD_MB * 1024 * 1024:
        await update.effective_message.reply_text("حجم فایل از محدودیت ربات بیشتره.")
        return
    suffix = path.suffix.lower()
    with path.open("rb") as f:
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            await update.effective_message.reply_photo(photo=f, caption=caption or None)
        elif suffix in {".mp4", ".mov", ".m4v", ".webm"}:
            await update.effective_message.reply_video(video=f, caption=caption or None)
        else:
            await update.effective_message.reply_document(document=f, caption=caption or None)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 🎧📥\n"
        "من می‌تونم آهنگ رو از فایل صوتی/ویدئویی تشخیص بدم و از لینک‌های عمومی "
        "اینستاگرام و تیک‌تاک رسانه دریافت کنم.\n\n"
        "/help راهنما\n"
        "/recognize راهنمای تشخیص آهنگ\n"
        "/download <link> دانلود رسانه\n"
        "/id نمایش شناسه چت"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 تشخیص آهنگ: یک فایل صوتی، ویس یا ویدئو بفرست.\n"
        "📥 دانلود: لینک عمومی پست اینستاگرام یا تیک‌تاک رو بفرست یا از دستور زیر استفاده کن:\n"
        "/download https://...\n"
        "🔗 در گروه، ربات می‌تونه لینک‌های عمومی رو خودکار بررسی کنه.\n\n"
        "نکته: محتوای خصوصی، نیازمند ورود، یا محدودشده دانلود نمی‌شه. "
        "لطفاً فقط محتوایی رو دریافت کن که اجازه دسترسی و استفاده ازش رو داری."
    )

async def recognize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("فایل صوتی، ویس یا ویدئویی که می‌خوای آهنگش شناسایی بشه رو بفرست.")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: `{update.effective_chat.id}`", parse_mode="Markdown")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("فعلاً تاریخچه ذخیره نمی‌شه؛ این دستور در نسخه بعدی اضافه می‌شه.")

async def process_recognition(update: Update, media_file) -> None:
    message = update.effective_message
    await message.reply_text("🎧 دارم آهنگ رو بررسی می‌کنم...")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        original = folder / "input_media"
        telegram_file = await media_file.get_file()
        await telegram_file.download_to_drive(custom_path=str(original))
        audio = folder / "sample.mp3"
        try:
            await asyncio.to_thread(extract_audio, original, audio)
            result = await asyncio.to_thread(acr_identify, audio)
            await message.reply_text(format_recognition(result))
        except FileNotFoundError:
            await message.reply_text("FFmpeg پیدا نشد. در Termux دستور `pkg install ffmpeg` رو اجرا کن.")
        except Exception as exc:
            await message.reply_text(f"خطا در تشخیص آهنگ: {str(exc)[:300]}")

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    media = message.video or message.audio or message.voice or message.document
    if not media:
        return
    mime = getattr(media, "mime_type", "") or ""
    if message.document and not (
        mime.startswith("audio/") or mime.startswith("video/")
        or (message.document.file_name or "").lower().endswith(
            (".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".mov", ".webm")
        )
    ):
        return
    await process_recognition(update, media)

async def download_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    message = update.effective_message

    if not valid_social_url(url):
        await message.reply_text("این لینک معتبر نیست یا از سایت‌های پشتیبانی‌شده نیست.")
        return

    await message.reply_text("⏬ در حال دانلود لینک...")

    with tempfile.TemporaryDirectory() as tmp:
        try:
            path = await asyncio.to_thread(
                download_public_media, url, Path(tmp)
            )
            await send_media(update, path, "✅ دانلود انجام شد.")
        except Exception as exc:
            await message.reply_text(f"خطا هنگام دانلود: {str(exc)[:350]}")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت دستور:\n/download https://... ")
        return
    await download_url(update, context, context.args[0])

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text or ""
    urls = URL_RE.findall(text)
    for url in urls:
        url = url.rstrip(".,!?)]}،؛")
        if valid_social_url(url):
            await download_url(update, context, url)
            return

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("Bot error:", context.error)

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN در فایل .env وارد نشده است.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("recognize", recognize_command))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(MessageHandler(
        filters.VIDEO | filters.AUDIO | filters.VOICE | filters.Document.ALL,
        media_handler
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
