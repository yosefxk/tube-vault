import os
import json
import asyncio
import uuid
import re
import urllib.parse
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import PORT, HOST, DOWNLOAD_DIR, BASE_DIR
from app.db import db
from app.downloader import extract_video_info, run_download_task, tasks_progress

app = FastAPI(title="TubeVault", description="Self-Hosted Media Downloader")

# CORS middleware for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def resolve_file_on_disk(filename: str) -> Optional[Path]:
    """Robustly locates a file on disk by name, decoded URL, or video ID pattern."""
    # 1. Direct match
    p = DOWNLOAD_DIR / filename
    if p.exists() and p.is_file():
        return p

    # 2. URL unquoted match
    unquoted = urllib.parse.unquote(filename)
    p2 = DOWNLOAD_DIR / unquoted
    if p2.exists() and p2.is_file():
        return p2

    # 3. Match by [video_id]
    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', filename) or re.search(r'\[([a-zA-Z0-9_-]{11})\]', unquoted)
    if match:
        vid = match.group(1)
        for f in DOWNLOAD_DIR.iterdir():
            if f.is_file() and f"[{vid}]" in f.name:
                return f

    return None

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    preset: Optional[str] = "quick_1080p"
    format_id: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(
            content=index_file.read_text(encoding="utf-8"),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return HTMLResponse(content="<h1>TubeVault API is running</h1>")

@app.post("/api/info")
async def get_info(req: InfoRequest):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL is required")
    try:
        info = await extract_video_info(req.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch media info: {str(e)}")

@app.post("/api/download")
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_download_task, task_id, req.url, req.preset, req.format_id)
    return {"task_id": task_id}

@app.get("/api/progress/{task_id}")
async def sse_progress(task_id: str):
    async def event_generator():
        while True:
            progress = tasks_progress.get(task_id)
            if not progress:
                yield f"data: {json.dumps({'status': 'waiting', 'percent': 0.0})}\n\n"
            else:
                yield f"data: {json.dumps(progress)}\n\n"
                if progress.get('status') in ['completed', 'failed']:
                    break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/history")
async def get_history(q: Optional[str] = Query(None)):
    return db.get_all(query=q)

@app.delete("/api/history/{record_id}")
async def delete_history(record_id: str):
    record = db.get_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    filename = record.get("filename")
    if filename:
        file_path = resolve_file_on_disk(filename)
        if file_path and file_path.exists():
            try:
                os.remove(file_path)
            except Exception:
                pass

    success = db.delete_entry(record_id)
    return {"success": success}

@app.get("/api/files/{filename:path}/download")
async def download_file(filename: str):
    file_path = resolve_file_on_disk(filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    
    real_filename = file_path.name
    # RFC 5987 / UTF-8 safe filename handling for mobile browsers
    encoded_filename = urllib.parse.quote(real_filename)
    
    return FileResponse(
        path=file_path,
        filename=real_filename,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )

@app.get("/api/files/{filename:path}/stream")
async def stream_file(filename: str, request: Request):
    file_path = resolve_file_on_disk(filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(
        path=file_path,
        media_type="video/mp4" if file_path.suffix.lower() in ['.mp4', '.mkv', '.webm'] else "audio/mpeg"
    )
