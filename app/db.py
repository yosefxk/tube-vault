import json
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.config import HISTORY_FILE

class HistoryDB:
    def __init__(self):
        self.lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        if not HISTORY_FILE.exists():
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def get_all(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.lock:
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
            
            # Sort newest first
            records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            if query:
                q = query.lower()
                records = [
                    r for r in records
                    if q in r.get("title", "").lower()
                    or q in r.get("uploader", "").lower()
                    or q in r.get("format_note", "").lower()
                ]

            return records

    def add_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []

            entry_id = str(uuid.uuid4())
            new_record = {
                "id": entry_id,
                "url": entry.get("url", ""),
                "video_id": entry.get("video_id", ""),
                "title": entry.get("title", "Unknown Title"),
                "uploader": entry.get("uploader", "Unknown Channel"),
                "thumbnail": entry.get("thumbnail", ""),
                "duration": entry.get("duration", 0),
                "duration_str": entry.get("duration_str", "00:00"),
                "format_id": entry.get("format_id", ""),
                "format_note": entry.get("format_note", "Standard"),
                "is_audio": entry.get("is_audio", False),
                "filename": entry.get("filename", ""),
                "filesize": entry.get("filesize", 0),
                "timestamp": datetime.now().isoformat()
            }

            records.append(new_record)

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)

            return new_record

    def get_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        records = self.get_all()
        for r in records:
            if r["id"] == record_id:
                return r
        return None

    def delete_entry(self, record_id: str) -> bool:
        with self.lock:
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                return False

            new_records = [r for r in records if r["id"] != record_id]
            if len(new_records) == len(records):
                return False

            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(new_records, f, indent=2)

            return True

db = HistoryDB()
