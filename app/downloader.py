import os
import asyncio
import uuid
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import yt_dlp
from app.config import DOWNLOAD_DIR
from app.db import db

# Active task progress store: task_id -> progress dict
tasks_progress: Dict[str, Dict[str, Any]] = {}

def format_bytes(bytes_num: Optional[int]) -> str:
    if not bytes_num:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def format_seconds(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def find_actual_downloaded_file(video_id: str, default_name: str) -> str:
    """Finds the real filename on disk matching video_id or default_name."""
    if (DOWNLOAD_DIR / default_name).exists():
        return default_name

    if video_id:
        for f in DOWNLOAD_DIR.iterdir():
            if f.is_file() and f"[{video_id}]" in f.name:
                return f.name

    return default_name

def extract_video_info(url: str) -> Dict[str, Any]:
    """Fetches video metadata & formats without downloading."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'no_playlist': True,
        'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web', 'tv']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    if 'entries' in info:
        # If a playlist link was given, take the first entry
        info = info['entries'][0]

    formats = []
    video_resolutions = set()
    
    # Process formats
    raw_formats = info.get('formats', [])
    for f in raw_formats:
        vcodec = f.get('vcodec', 'none')
        acodec = f.get('acodec', 'none')
        height = f.get('height')
        ext = f.get('ext', '')
        format_id = f.get('format_id', '')
        filesize = f.get('filesize') or f.get('filesize_approx')

        # Video formats with video stream
        if vcodec != 'none' and height:
            res_key = f"{height}p"
            if res_key not in video_resolutions:
                video_resolutions.add(res_key)
                formats.append({
                    'format_id': format_id,
                    'type': 'video',
                    'resolution': res_key,
                    'height': height,
                    'ext': ext,
                    'note': f"{res_key} Video ({ext.upper()})",
                    'filesize_str': format_bytes(filesize) if filesize else "Variable"
                })

    # Sort formats by height descending
    formats.sort(key=lambda x: x.get('height', 0), reverse=True)

    # Standard presets
    presets = [
        {'id': 'quick_mp3', 'label': '⚡ Quick MP3 (320kbps)', 'is_audio': True, 'type': 'audio', 'ext': 'mp3'},
        {'id': 'quick_1080p', 'label': '⚡ Quick 1080p Video', 'is_audio': False, 'type': 'video', 'ext': 'mp4'},
        {'id': 'best_video', 'label': '🔥 Max Quality Video (4K / Best)', 'is_audio': False, 'type': 'video', 'ext': 'mp4'},
        {'id': 'm4a_audio', 'label': '🎵 Best AAC / M4A Audio', 'is_audio': True, 'type': 'audio', 'ext': 'm4a'},
    ]

    return {
        'id': info.get('id', ''),
        'title': info.get('title', 'Unknown Title'),
        'uploader': info.get('uploader', 'Unknown Uploader'),
        'thumbnail': info.get('thumbnail', ''),
        'duration': info.get('duration', 0),
        'duration_str': format_seconds(info.get('duration', 0)),
        'view_count': info.get('view_count', 0),
        'formats': formats,
        'presets': presets
    }

async def run_download_task(task_id: str, url: str, preset: str = "quick_1080p", custom_format_id: Optional[str] = None):
    """Executes the download task in threadpool and streams progress."""
    tasks_progress[task_id] = {
        'status': 'starting',
        'percent': 0.0,
        'speed_str': '0 MB/s',
        'eta_str': 'Calculating...',
        'downloaded_str': '0 MB',
        'total_str': '0 MB',
        'filename': '',
        'error': None
    }

    def progress_hook(d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0

            percent = (downloaded / total_bytes * 100) if total_bytes > 0 else 0.0

            tasks_progress[task_id].update({
                'status': 'downloading',
                'percent': round(percent, 1),
                'downloaded_str': format_bytes(downloaded),
                'total_str': format_bytes(total_bytes),
                'speed_str': f"{format_bytes(speed)}/s" if speed else "0 B/s",
                'eta_str': f"{eta}s" if eta else "Calculating..."
            })
        elif d['status'] == 'finished':
            tasks_progress[task_id].update({
                'status': 'converting',
                'percent': 99.0,
                'eta_str': 'Finalizing file...'
            })

    def _execute():
        out_template = str(DOWNLOAD_DIR / '%(title)s [%(id)s].%(ext)s')
        
        ydl_opts: Dict[str, Any] = {
            'outtmpl': out_template,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'no_playlist': True,
            'overwrites': True,
            'retries': 10,
            'fragment_retries': 10,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android', 'web', 'tv']}}
        }

        is_audio = False
        format_note = "Standard"

        if preset == 'quick_mp3':
            is_audio = True
            format_note = "Audio MP3 (320kbps)"
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }]
            })
        elif preset == 'm4a_audio':
            is_audio = True
            format_note = "Audio M4A"
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }]
            })
        elif preset == 'quick_1080p':
            format_note = "1080p Video"
            ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'
        elif preset == 'best_video':
            format_note = "Max Quality Video"
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'
        elif custom_format_id:
            format_note = f"Custom Format ({custom_format_id})"
            ydl_opts['format'] = f"{custom_format_id}+bestaudio/best/{custom_format_id}/best"
            ydl_opts['merge_output_format'] = 'mp4'
        else:
            format_note = "Best Video"
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'entries' in info:
                info = info['entries'][0]

            video_id = info.get('id', '')
            raw_filename = ydl.prepare_filename(info)

            # Adjust extension based on conversion
            if preset == 'quick_mp3':
                raw_filename = os.path.splitext(raw_filename)[0] + '.mp3'
            elif preset == 'm4a_audio':
                raw_filename = os.path.splitext(raw_filename)[0] + '.m4a'
            elif ydl_opts.get('merge_output_format') == 'mp4':
                raw_filename = os.path.splitext(raw_filename)[0] + '.mp4'

            # Accurately resolve filename on disk (handles unicode/pipe sanitization)
            basename = find_actual_downloaded_file(video_id, os.path.basename(raw_filename))
            actual_filepath = DOWNLOAD_DIR / basename
            filesize = os.path.getsize(actual_filepath) if actual_filepath.exists() else 0

            # Save to persistent history database
            history_record = db.add_entry({
                'url': url,
                'video_id': video_id,
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown Uploader'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'duration_str': format_seconds(info.get('duration', 0)),
                'format_id': custom_format_id or preset,
                'format_note': format_note,
                'is_audio': is_audio,
                'filename': basename,
                'filesize': filesize
            })

            tasks_progress[task_id].update({
                'status': 'completed',
                'percent': 100.0,
                'filename': basename,
                'record_id': history_record['id'],
                'eta_str': 'Complete!'
            })

    try:
        await asyncio.to_thread(_execute)
    except Exception as e:
        tasks_progress[task_id].update({
            'status': 'failed',
            'error': str(e)
        })
