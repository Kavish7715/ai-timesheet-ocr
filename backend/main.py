"""
main.py — FastAPI entry point for the AI Timesheet Automation System.

Endpoints:
  GET  /health          — health check
  POST /upload-timesheet — accept image, run OCR + AI parsing, return JSON
"""

import sys
import os
import uuid
import tempfile
from pathlib import Path

# Force UTF-8 encoding on Windows to handle Unicode characters from
# EasyOCR/tqdm progress bars (e.g. block chars like █ = U+2588).
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Load .env (GEMINI_API_KEY etc.) before any module imports
from dotenv import load_dotenv
load_dotenv()

import httpx

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ocr import extract_text, warmup_reader
from parser import parse_timesheet_image, warmup_pipeline
from utils import clean_ocr_text

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Timesheet Automation System",
    description="Extract structured work-hour data from timesheet screenshots using OCR + AI.",
    version="1.0.1",
)

# Allow requests from the React dev server (localhost:5173) and any production URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp directory for uploaded images
UPLOAD_DIR = Path(tempfile.gettempdir()) / "timesheet_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Accepted MIME types
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
MAX_FILE_SIZE_MB = 20

# External Timesheet API config (loaded from .env)
TIMESHEET_API_URL = os.environ.get("TIMESHEET_API_URL", "")
TIMESHEET_API_KEY = os.environ.get("TIMESHEET_API_KEY", "")

# Retry configuration for external API (cold-start can take 30-45s)
MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # seconds between retries


# ---------------------------------------------------------------------------
# Pydantic models for /submit-timesheet
# ---------------------------------------------------------------------------

class TimesheetEntry(BaseModel):
    date: str | None = None
    login: str | None = None
    logout: str | None = None
    hours: float | None = None
    confidence: str | None = None

class TimesheetPayload(BaseModel):
    employee_name: str | None = "Unknown"
    entries: list[TimesheetEntry] = []
    total_entries: int = 0
    parse_source: str = "unknown"


# ---------------------------------------------------------------------------
# Startup + Endpoints
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def preload_models():
    """
    Warm OCR and parser models at startup.
    This avoids long first-request initialization timeouts.
    """
    print("[System] Initializing AI components and preloading models...")
    try:
        warmup_reader()
        warmup_pipeline()
        print("[System] All models ready.")
    except Exception as exc:
        print(f"[System] Warning: Model preload partially failed: {exc}")

@app.get("/health")
async def health_check():
    """Simple health check — returns service status."""
    return {"status": "ok", "service": "AI Timesheet Automation System"}


@app.post("/upload-timesheet")
async def upload_timesheet(file: UploadFile = File(...)):
    """
    Accept an uploaded image, perform OCR, run AI parsing, and return
    a structured JSON object with timesheet entries.
    """
    # --- Validate file type ---
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Please upload a JPEG, PNG, WEBP, BMP, or TIFF image.",
        )

    # --- Read file content ---
    content = await file.read()

    # --- Validate file size ---
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
        )

    # --- Save to temp file ---
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        print(f"[API] Saved upload to {temp_path} ({size_mb:.2f} MB)")

        raw_text = ""
        cleaned_text = ""

        # Vision-first strategy: OCR is only triggered if direct vision parsing fails
        parsed = parse_timesheet_image(str(temp_path), ocr_text="")

        if not parsed.get("entries"):
            print("[Process] Vision returned no entries - initiating EasyOCR fallback...")
            raw_text = extract_text(str(temp_path))
            cleaned_text = clean_ocr_text(raw_text)
            parsed = parse_timesheet_image(str(temp_path), ocr_text=cleaned_text)

        print(f"[Process] Analysis complete | Source: {parsed.get('parse_source')} | Entries: {parsed.get('total_entries')}")

        # --- Build response ---
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "raw_text": cleaned_text,  # empty string if vision succeeded without OCR
            "result": parsed,
        })

    except Exception as exc:
        print(f"[API] Error processing upload: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        # Always clean up the temp file
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
            print(f"[API] Cleaned up temp file {temp_path}")


@app.post("/submit-timesheet")
async def submit_timesheet(payload: TimesheetPayload):
    """
    Forward parsed timesheet data to the external database API.
    Includes retry logic for Render cold-start wake-up (30-45s).
    """
    if not TIMESHEET_API_URL or not TIMESHEET_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="External timesheet API is not configured. "
                   "Set TIMESHEET_API_URL and TIMESHEET_API_KEY in your .env file.",
        )

    headers = {
        "x-api-key": TIMESHEET_API_KEY,
        "Content-Type": "application/json",
    }

    body = payload.model_dump()

    # Prepare entries for the external API:
    # - Replace null/empty login and logout with '00:00' (valid HH:mm placeholder)
    # - Skip entries where hours is not a positive number
    valid_entries = []
    for entry in body.get("entries", []):
        hours = entry.get("hours")

        # Skip if hours is missing or not positive
        if hours is None or float(hours) <= 0:
            continue

        # Default null login/logout to '00:00' (API requires valid HH:mm)
        entry["login"] = entry.get("login") or "00:00"
        entry["logout"] = entry.get("logout") or "00:01"

        valid_entries.append(entry)
    body["entries"] = valid_entries
    body["total_entries"] = len(valid_entries)

    if not valid_entries:
        raise HTTPException(
            status_code=422,
            detail="No valid entries to upload. All entries have missing or non-positive hours.",
        )

    print(f"[Submit] Sending {body.get('total_entries', 0)} entries for '{body.get('employee_name')}' to external API…")

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Generous timeout: 60s connect + 60s read to handle cold starts
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=60.0)) as client:
                response = await client.post(
                    TIMESHEET_API_URL,
                    headers=headers,
                    json=body,
                )

            if response.status_code in (200, 201):
                try:
                    resp_data = response.json()
                except Exception:
                    resp_data = {"raw": response.text}

                print(f"[Submit] ✓ Success on attempt {attempt} — status {response.status_code}")
                return JSONResponse(content={
                    "success": True,
                    "message": "Timesheet data uploaded to database successfully.",
                    "api_response": resp_data,
                })

            # Non-success status code — may be a cold-start 502/503
            last_error = f"API returned status {response.status_code}: {response.text[:300]}"
            print(f"[Submit] Attempt {attempt}/{MAX_RETRIES} failed — {last_error}")

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            last_error = f"Connection error: {exc}"
            print(f"[Submit] Attempt {attempt}/{MAX_RETRIES} — {last_error}")
        except Exception as exc:
            last_error = str(exc)
            print(f"[Submit] Attempt {attempt}/{MAX_RETRIES} — unexpected error: {last_error}")

        # Wait before retrying (unless this was the last attempt)
        if attempt < MAX_RETRIES:
            delay = RETRY_DELAYS[attempt - 1]
            print(f"[Submit] Retrying in {delay}s (server may be waking up)…")
            import asyncio
            await asyncio.sleep(delay)

    # All retries exhausted
    print(f"[Submit] ✗ All {MAX_RETRIES} attempts failed.")
    raise HTTPException(
        status_code=502,
        detail=f"Could not reach the external timesheet API after {MAX_RETRIES} attempts. "
               f"Last error: {last_error}. "
               f"The server may be in sleep mode — please try again in 30-45 seconds.",
    )
