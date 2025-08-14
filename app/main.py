import os
import uuid
import zipfile
import asyncio
import shutil
import re
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
import subprocess

app = FastAPI()

# Folders expected by your bash script
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORIGZIP = os.path.join(BASE_DIR, "originalzip")
ORIG = os.path.join(BASE_DIR, "original")
RESIZED = os.path.join(BASE_DIR, "resized")
RESIZEDZIP = os.path.join(BASE_DIR, "resizedzip")

for d in (ORIGZIP, ORIG, RESIZED, RESIZEDZIP):
    os.makedirs(d, exist_ok=True)

# In-memory job store (swap to Redis if you want durability)
jobs: Dict[str, Dict[str, Any]] = {}

# Serve the static test UI
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.post("/jobs")
async def create_job(
    size: int = Form(..., description="Canvas size, e.g. 1550"),
    resize: int = Form(..., description="Max dimension, e.g. 1200"),
    zipfile_upload: UploadFile = File(...),
):
    # Save uploaded zip
    safe_name = f"{uuid.uuid4()}_{zipfile_upload.filename}"
    saved_path = os.path.join(ORIGZIP, safe_name)
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(zipfile_upload.file, f)

    # Count how many images we expect (jpg/jpeg/png)
    total_images = 0
    try:
        with zipfile.ZipFile(saved_path, "r") as z:
            for info in z.infolist():
                if not info.is_dir():
                    name = info.filename.lower()
                    if name.endswith((".jpg", ".jpeg", ".png")):
                        total_images += 1
    except Exception:
        # If counting fails, fall back to unknown total
        total_images = 0

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": total_images,
        "processed": 0,
        "phase": "queued",
        "zip_path": None,
        "error": None,
    }

    # Launch background task
    asyncio.create_task(run_process(job_id, size, resize))

    return {"job_id": job_id}


async def run_process(job_id: str, size: int, resize: int):
    job = jobs[job_id]
    job["status"] = "running"
    job["phase"] = "unzipping"

    # Start process.sh and read its stdout progressively
    # It will unzip itself, process files, then print the output ZIP path as last line
    cmd = ["bash", os.path.join(BASE_DIR, "process.sh"), str(size), str(resize)]

    # Use Popen to stream output lines
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=BASE_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )

    processed_re = re.compile(r"^Processed:\s+(.+)")
    output_zip: Optional[str] = None

    # Heuristic phases
    # - when we see first "Processed:" -> phase = processing
    # - final line ends with ".zip" -> done
    job["phase"] = "processing"

    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()

            # Track processed count from script output
            m = processed_re.match(text)
            if m:
                job["processed"] = job.get("processed", 0) + 1
                if job["total"] > 0:
                    job["progress"] = int(job["processed"] * 100 / job["total"])
                else:
                    # If total unknown, just cap at 95% while processing
                    job["progress"] = min(95, job.get("progress", 0) + 1)
            elif text.endswith(".zip"):
                # Last echo from script should be the zip path
                candidate = text
                if os.path.isabs(candidate):
                    output_zip = candidate
                else:
                    output_zip = os.path.join(BASE_DIR, candidate)
            # Optionally store last line seen for debugging
            job["last"] = text

        rc = await proc.wait()
        if rc != 0:
            job["status"] = "error"
            job["phase"] = "failed"
            job["error"] = f"process.sh exited with code {rc}"
            job["progress"] = 0
            return

        # Complete
        job["status"] = "done"
        job["phase"] = "zipping"
        if output_zip and os.path.exists(output_zip):
            job["zip_path"] = output_zip
        # Mark 100% if we have total
        if job["total"] > 0:
            job["progress"] = 100
        else:
            job["progress"] = max(job["progress"], 100)
        job["phase"] = "done"

    except Exception as e:
        job["status"] = "error"
        job["phase"] = "failed"
        job["error"] = str(e)
        job["progress"] = 0


@app.websocket("/ws/{job_id}")
async def job_ws(ws: WebSocket, job_id: str):
    await ws.accept()
    try:
        while True:
            if job_id not in jobs:
                await ws.send_json({"error": "job not found"})
                await asyncio.sleep(1)
                continue
            job = jobs[job_id].copy()
            # Compose a nice payload for the UI
            payload = {
                "status": job["status"],
                "progress": job["progress"],
                "processed": job["processed"],
                "total": job["total"],
                "phase": job["phase"],
                "download_url": f"/download/{job_id}"
                if (job["status"] == "done" and job.get("zip_path"))
                else None,
                "error": job["error"],
            }
            await ws.send_json(payload)
            if job["status"] in ("done", "error"):
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


@app.get("/download/{job_id}")
def download(job_id: str):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done" or not job.get("zip_path"):
        return HTMLResponse("Job not ready or not found", status_code=404)
    path = job["zip_path"]
    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="application/zip")
