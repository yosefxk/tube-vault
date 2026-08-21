import os
import re
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from app.config import (
    DOWNLOAD_DIR,
    DATA_DIR,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_SESSION_STRING,
    TELEGRAM_SESSION_FILE
)
from app.db import db

_client = None
_client_lock = asyncio.Lock()

TELEGRAM_URL_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?(?:c/(\d+)|([a-zA-Z0-9_]+))/(\d+)'
)

def is_telegram_url(url: str) -> bool:
    if not url:
        return False
    return bool(TELEGRAM_URL_PATTERN.search(url.strip()))

def parse_telegram_url(url: str) -> Tuple[Optional[str], Optional[int], bool]:
    """Extracts (channel, message_id, is_private_numeric_channel) from a t.me URL."""
    match = TELEGRAM_URL_PATTERN.search(url.strip())
    if not match:
        return None, None, False
    
    private_cid, username, msg_id = match.groups()
    if private_cid:
        # Private channel IDs in t.me/c/123456789/21 need -100 prefix for Telethon
        cid = int(f"-100{private_cid}")
        return str(cid), int(msg_id), True
    else:
        return username, int(msg_id), False

async def get_telegram_client():
    """Initializes and connects the Telethon client instance."""
    global _client
    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            raise ValueError(
                "Telegram support requires TELEGRAM_API_ID and TELEGRAM_API_HASH. "
                "Add them to your environment variables in docker-compose.yml (get free keys at https://my.telegram.org)."
            )

        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except ImportError:
            raise RuntimeError("Telethon library is not installed. Please reinstall requirements.")

        api_id = int(TELEGRAM_API_ID)
        api_hash = str(TELEGRAM_API_HASH).strip()

        if TELEGRAM_SESSION_STRING:
            session = StringSession(TELEGRAM_SESSION_STRING.strip())
        else:
            session = str(TELEGRAM_SESSION_FILE)

        _client = TelegramClient(session, api_id, api_hash)
        
        if TELEGRAM_BOT_TOKEN:
            await _client.start(bot_token=TELEGRAM_BOT_TOKEN.strip())
        else:
            await _client.connect()

        return _client

def format_bytes(bytes_num: Optional[int]) -> str:
    if not bytes_num:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def format_seconds(seconds: Optional[Any]) -> str:
    if seconds is None:
        return "00:00"
    try:
        sec_float = float(seconds)
        if sec_float <= 0:
            return "00:00"
        sec_int = int(round(sec_float))
        m, s = divmod(sec_int, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return "00:00"

async def extract_telegram_info(url: str) -> Dict[str, Any]:
    """Fetches Telegram message metadata without downloading the full media."""
    channel_key, msg_id, is_private = parse_telegram_url(url)
    if not channel_key or not msg_id:
        raise ValueError("Invalid Telegram post URL format.")

    client = await get_telegram_client()

    # Resolve channel entity
    try:
        entity = await client.get_entity(int(channel_key) if is_private else channel_key)
    except Exception as e:
        raise ValueError(f"Could not access Telegram channel '{channel_key}': {str(e)}")

    # Fetch specific message
    messages = await client.get_messages(entity, ids=[msg_id])
    if not messages or not messages[0]:
        raise ValueError(f"Message ID {msg_id} not found in channel.")

    message = messages[0]
    if not message.media:
        raise ValueError("This Telegram post does not contain any video, audio, or downloadable media file.")

    # Determine filename, duration, size, resolution
    filename = None
    duration = 0
    height = None
    width = None
    filesize = 0
    is_audio = False
    ext = "mp4"

    if getattr(message, 'file', None):
        filename = message.file.name
        filesize = message.file.size or 0
        duration = message.file.duration or 0
        if message.file.ext:
            ext = message.file.ext.lstrip('.').lower()

    if getattr(message, 'video', None):
        height = message.video.h
        width = message.video.w
        duration = message.video.duration or duration
        ext = "mp4"
    elif getattr(message, 'audio', None) or getattr(message, 'voice', None):
        is_audio = True
        ext = ext if ext in ['mp3', 'm4a', 'ogg', 'wav', 'flac'] else "mp3"

    channel_title = getattr(entity, 'title', None) or getattr(entity, 'username', None) or str(channel_key)
    raw_text = (message.text or message.message or "").strip()
    caption_line = raw_text.split('\n')[0][:80] if raw_text else ""

    display_title = filename or caption_line or f"{channel_title} - Post #{msg_id}"
    res_str = f"{height}p" if height else "Original Quality"

    formats = [{
        'format_id': 'tg_direct',
        'type': 'audio' if is_audio else 'video',
        'resolution': res_str,
        'height': height or 1080,
        'ext': ext,
        'note': f"Telegram {res_str} ({ext.upper()})",
        'filesize_str': format_bytes(filesize) if filesize else "Variable"
    }]

    presets = [
        {
            'id': 'quick_tg',
            'label': f"⚡ Download Telegram {ext.upper()}",
            'is_audio': is_audio,
            'type': 'audio' if is_audio else 'video',
            'ext': ext
        }
    ]

    return {
        'id': f"tg_{channel_key}_{msg_id}",
        'title': display_title,
        'uploader': f"Telegram: {channel_title}",
        'thumbnail': '',
        'duration': duration,
        'duration_str': format_seconds(duration),
        'view_count': getattr(message, 'views', 0) or 0,
        'formats': formats,
        'presets': presets
    }

async def run_telegram_download_task(
    task_id: str,
    tasks_progress_store: Dict[str, Any],
    url: str,
    preset: str = "quick_tg",
    custom_format_id: Optional[str] = None
):
    """Downloads Telegram media with real-time SSE progress streaming."""
    tasks_progress_store[task_id] = {
        'status': 'starting',
        'percent': 0.0,
        'speed_str': '0 MB/s',
        'eta_str': 'Calculating...',
        'downloaded_str': '0 MB',
        'total_str': '0 MB',
        'filename': '',
        'error': None
    }

    try:
        channel_key, msg_id, is_private = parse_telegram_url(url)
        if not channel_key or not msg_id:
            raise ValueError("Invalid Telegram URL format.")

        client = await get_telegram_client()
        entity = await client.get_entity(int(channel_key) if is_private else channel_key)
        messages = await client.get_messages(entity, ids=[msg_id])

        if not messages or not messages[0] or not messages[0].media:
            raise ValueError("No downloadable media found in this Telegram message.")

        message = messages[0]
        channel_title = getattr(entity, 'title', None) or getattr(entity, 'username', None) or str(channel_key)

        # Generate target filename
        ext = "mp4"
        if getattr(message, 'file', None) and message.file.ext:
            ext = message.file.ext.lstrip('.').lower()

        base_name = getattr(message.file, 'name', None)
        if not base_name:
            caption = (message.text or message.message or "").strip().split('\n')[0][:50]
            clean_caption = re.sub(r'[\\/*?:"<>|]', "", caption).strip()
            clean_channel = re.sub(r'[\\/*?:"<>|]', "", channel_title).strip()
            base_name = f"{clean_channel} - {clean_caption or f'Post_{msg_id}'}.{ext}"

        # Ensure valid filename on disk
        clean_filename = re.sub(r'[\\/*?:"<>|]', "", base_name)
        target_path = DOWNLOAD_DIR / clean_filename

        total_bytes = getattr(message.file, 'size', 0) or 0
        last_time = time.time()
        last_downloaded = 0

        def progress_callback(current, total):
            nonlocal last_time, last_downloaded
            now = time.time()
            dt = now - last_time
            if dt >= 0.4 or current == total:
                speed = (current - last_downloaded) / dt if dt > 0 else 0
                eta = (total - current) / speed if speed > 0 else None
                percent = (current / total * 100) if total > 0 else 0.0

                tasks_progress_store[task_id].update({
                    'status': 'downloading',
                    'percent': round(percent, 1),
                    'downloaded_str': format_bytes(current),
                    'total_str': format_bytes(total),
                    'speed_str': f"{format_bytes(speed)}/s" if speed else "0 B/s",
                    'eta_str': format_seconds(eta) if eta is not None and eta > 0 else "Calculating..."
                })
                last_time = now
                last_downloaded = current

        # Execute download via Telethon
        downloaded_file = await client.download_media(
            message,
            file=str(target_path),
            progress_callback=progress_callback
        )

        if not downloaded_file or not Path(downloaded_file).exists():
            raise RuntimeError("Telegram download did not complete successfully.")

        final_path = Path(downloaded_file)
        real_basename = final_path.name
        filesize = final_path.stat().st_size
        duration = getattr(message.file, 'duration', 0) or 0
        is_audio = getattr(message, 'audio', None) is not None or getattr(message, 'voice', None) is not None

        history_record = db.add_entry({
            'url': url,
            'video_id': f"tg_{channel_key}_{msg_id}",
            'title': real_basename,
            'uploader': f"Telegram: {channel_title}",
            'thumbnail': '',
            'duration': duration,
            'duration_str': format_seconds(duration),
            'format_id': 'telegram',
            'format_note': f"Telegram ({ext.upper()})",
            'is_audio': is_audio,
            'filename': real_basename,
            'filesize': filesize
        })

        tasks_progress_store[task_id].update({
            'status': 'completed',
            'percent': 100.0,
            'filename': real_basename,
            'record_id': history_record['id'],
            'eta_str': 'Complete!'
        })

    except Exception as e:
        tasks_progress_store[task_id].update({
            'status': 'failed',
            'error': str(e)
        })
