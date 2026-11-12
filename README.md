# Music & Media Telegram Bot

## Features
- Recognizes songs from Telegram audio, voice, video, and supported audio/video documents (ACRCloud credentials required).
- Downloads publicly accessible Instagram and TikTok posts through yt-dlp.
- Detects supported Instagram/TikTok links posted in chats and groups.
- Supports /start, /help, /recognize, /download, /id, and /history (history is currently a placeholder).

## Important limits
- It does not access private posts, bypass logins, or defeat platform restrictions.
- Use it only for media you have permission to access and share.
- Android may stop background apps; this setup is best for testing, not guaranteed 24/7 hosting.

## Android / Termux setup
1. Install Termux from its official F-Droid listing: https://f-droid.org/packages/com.termux/
2. In Termux run:
   ```sh
   pkg update && pkg upgrade -y
   pkg install python ffmpeg nano -y
   ```
3. Put these files in one folder, then enter that folder in Termux.
4. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
5. Create your config:
   ```sh
   cp .env.example .env
   nano .env
   ```
6. Paste your Telegram bot token after `BOT_TOKEN=`.
7. To enable music recognition, fill in the three ACRCloud values in `.env`. Without them, link downloading still works.
8. Run:
   ```sh
   python bot.py
   ```

## Group setup
- Add the bot to the group.
- If you want it to read ordinary group messages (not only commands or replies), open BotFather, use `/setprivacy`, select the bot, and disable Group Privacy.
- Remove and re-add the bot to the group if Telegram asks you to refresh permissions.

## Get a Telegram bot token
Talk to the official @BotFather account in Telegram and use `/newbot`. Keep the token private. Never post it in a group or send it to anyone.

## ACRCloud
Create an ACRCloud account/project and copy the host, access key, and access secret into `.env`.
s
