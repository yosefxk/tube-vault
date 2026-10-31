import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.config import DOWNLOAD_DIR
from app.main import resolve_file_on_disk
from app.downloader import (
    validate_media_url,
    validate_format_id,
    extract_video_info,
    tasks_progress,
    BoundedTasksProgress
)

def test_resolve_file_on_disk_traversal_prevention(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.DOWNLOAD_DIR", tmp_path)
    
    # Attempting to access parent files outside DOWNLOAD_DIR must return None
    assert resolve_file_on_disk("../../etc/passwd") is None
    assert resolve_file_on_disk("..%2f..%2f..%2fetc%2fpasswd") is None
    assert resolve_file_on_disk("../app/main.py") is None

    # Legitimate file inside DOWNLOAD_DIR should resolve
    test_file = tmp_path / "sample_video [abc12345678].mp4"
    test_file.write_text("dummy content")
    resolved = resolve_file_on_disk("sample_video [abc12345678].mp4")
    assert resolved is not None
    assert resolved.name == "sample_video [abc12345678].mp4"


def test_validate_media_url_ssrf():
    # Invalid schemes
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_media_url("ftp://example.com/video")
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_media_url("file:///etc/passwd")

    # Localhost / Private IPs
    with pytest.raises(ValueError, match="private/internal IP"):
        validate_media_url("http://127.0.0.1:8000/test")
    with pytest.raises(ValueError, match="private/internal IP"):
        validate_media_url("http://localhost/test")

def test_validate_format_id():
    validate_format_id("137")
    validate_format_id("bestvideo.1")
    validate_format_id("mp4_1080p-60")

    with pytest.raises(ValueError, match="Invalid format_id"):
        validate_format_id("137; rm -rf /")
    with pytest.raises(ValueError, match="Invalid format_id"):
        validate_format_id("format|id")

def test_empty_playlist_handling():
    with patch("yt_dlp.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {"entries": []}
        mock_ydl.return_value.__enter__.return_value = mock_instance

        with patch("app.downloader.validate_media_url"):
            with pytest.raises(ValueError, match="Playlist contains no accessible entries"):
                extract_video_info("https://youtube.com/playlist?list=EMPTY")

def test_bounded_tasks_progress():
    bp = BoundedTasksProgress(maxsize=10)
    for i in range(25):
        bp[f"task_{i}"] = {"percent": i}
    assert len(bp) == 10
    assert "task_0" not in bp
    assert "task_24" in bp
