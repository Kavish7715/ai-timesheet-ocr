"""
parser.py — AI Parsing module using Google Gemini 2.5 Flash (Vision + Text).

Strategy:
  1. PRIMARY  — Send the raw image directly to gemini-2.5-flash (vision mode).
               This is the most accurate path — no OCR step needed.
  2. FALLBACK A — If vision fails, send the EasyOCR-extracted text to gemini-2.5-flash.
  3. FALLBACK B — If Gemini is unavailable entirely, use regex parsing on OCR text.
  4. Post-process all results: validate times/dates, compute missing hours, add confidence.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from utils import validate_time_format, normalise_date, calculate_hours, clean_ocr_text

# ---------------------------------------------------------------------------
# Gemini 2.5 Flash client — uses the newer `google-genai` SDK
# ---------------------------------------------------------------------------
_gemini_client = None


def _get_gemini_client():
    """Lazy-load and return the Gemini client. Returns None if unavailable."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    try:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("[Parser] GEMINI_API_KEY not set — will use regex fallback.")
            return None
        _gemini_client = genai.Client(api_key=api_key)
        print("[Parser] Gemini 2.5 Flash client ready.")
        return _gemini_client
    except Exception as exc:
        print(f"[Parser] Gemini unavailable: {exc}. Will use regex fallback.")
        return None


def warmup_pipeline():
    """Preload Gemini client during app startup (lightweight — just validates API key)."""
    client = _get_gemini_client()
    if client:
        print("[Parser] Gemini client warmed up successfully.")
    else:
        print("[Parser] Gemini client not available. Regex fallback will be used.")


# ---------------------------------------------------------------------------
# Shared JSON prompt
# ---------------------------------------------------------------------------

_JSON_SCHEMA = (
    '{"employee_name": "Full Name", "entries": [{"date": "YYYY-MM-DD", "login": "HH:MM", "logout": "HH:MM", "hours": 0.0}]}'
)

_BASE_INSTRUCTIONS = (
    "You are a timesheet data extraction assistant.\n"
    "Extract ALL timesheet entries and the employee's name. Return ONLY a valid JSON object — "
    "no markdown, no explanation, just raw JSON:\n\n"
    f"{_JSON_SCHEMA}\n\n"
    "Rules:\n"
    "- CRITICAL: Extract the 'employee_name' from the timesheet (usually at the top). If you cannot find it, use null.\n"
    "- Use 24-hour format for login/logout (e.g. 09:00, 17:30)\n"
    "- If a value is missing, empty, or just dashes (e.g. absent/weekend), use null for login/logout and 0 for hours.\n"
    "- Use YYYY-MM-DD format for dates\n"
    "- If hours is explicit, use it; otherwise calculate from login/logout\n"
    "- Include ALL entries found, even empty days\n\n"
)

_VISION_PROMPT = _BASE_INSTRUCTIONS + "JSON:"

def _build_text_prompt(text: str) -> str:
    return _BASE_INSTRUCTIONS + f"Timesheet Text:\n{text}\n\nJSON:"

def _parse_gemini_response(output: str) -> Optional[dict]:
    """Extract and parse the JSON object from a Gemini response string."""
    output = output.strip()
    # Strip markdown code fences if present
    output = re.sub(r"^```(?:json)?\s*", "", output, flags=re.IGNORECASE)
    output = re.sub(r"\s*```$", "", output)
    json_match = re.search(r"\{.*\}", output, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            if "entries" in parsed and isinstance(parsed["entries"], list):
                return parsed
        except json.JSONDecodeError as exc:
            print(f"[Parser] JSON decode error: {exc}")
    return None


# ---------------------------------------------------------------------------
# Vision Parse — image bytes sent directly to Gemini
# ---------------------------------------------------------------------------

def _try_gemini_vision(image_path: str) -> Optional[dict]:
    """
    Send the raw image to Gemini 2.5 Flash for direct vision-based extraction.
    Returns parsed dict on success, None on failure.
    """
    client = _get_gemini_client()
    if client is None:
        return None

    try:
        from google.genai import types

        image_bytes = Path(image_path).read_bytes()

        # Determine MIME type from extension
        ext = Path(image_path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp",
            ".bmp": "image/bmp", ".tiff": "image/tiff", ".tif": "image/tiff",
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        print(f"[Parser] Sending image to Gemini Vision ({mime_type}, {len(image_bytes)//1024} KB)…")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                _VISION_PROMPT,
            ],
        )
        output = response.text
        result = _parse_gemini_response(output)
        if result:
            print(f"[Parser] Gemini Vision returned {len(result['entries'])} entries.")
            return result
        print("[Parser] Gemini Vision response could not be parsed as JSON.")
    except Exception as exc:
        print(f"[Parser] Gemini Vision error: {exc}")
    return None


# ---------------------------------------------------------------------------
# Text-only Gemini Parse — OCR text sent to Gemini as text
# ---------------------------------------------------------------------------

def _try_gemini_text(text: str) -> Optional[dict]:
    """
    Send OCR-extracted text to Gemini 2.5 Flash for text-based extraction.
    Returns parsed dict on success, None on failure.
    """
    client = _get_gemini_client()
    if client is None:
        return None

    prompt = _build_text_prompt(text)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        output = response.text
        result = _parse_gemini_response(output)
        if result:
            print(f"[Parser] Gemini Text returned {len(result['entries'])} entries.")
            return result
        print("[Parser] Gemini Text response could not be parsed as JSON.")
    except Exception as exc:
        print(f"[Parser] Gemini Text error: {exc}")
    return None


# ---------------------------------------------------------------------------
# Regex Fallback
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b",
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?)\b",
    r"\b((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})\b",
    r"\b((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\b",
]

_TIME_RANGE_PATTERN = re.compile(
    r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\s*[-–—to]+\s*(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)",
    re.IGNORECASE,
)
_DURATION_PATTERN = re.compile(
    r"(\d{1,2})\s*h(?:ours?)?\s*(\d{0,2})\s*m(?:in(?:utes?)?)?", re.IGNORECASE
)
_DURATION_DECIMAL = re.compile(r"(\d+(?:\.\d+)?)\s*h(?:ours?|rs?)", re.IGNORECASE)
_STANDALONE_TIME = re.compile(r"\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b", re.IGNORECASE)


def _extract_duration(line: str) -> Optional[float]:
    m = _DURATION_PATTERN.search(line)
    if m:
        return round(int(m.group(1)) + (int(m.group(2)) if m.group(2) else 0) / 60, 2)
    m = _DURATION_DECIMAL.search(line)
    if m:
        return round(float(m.group(1)), 2)
    return None


def _regex_parse(text: str) -> dict:
    """Rule-based fallback parser."""
    lines = text.split("\n")
    entries = []
    current_date = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        for pat in _DATE_PATTERNS:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                current_date = normalise_date(m.group(1))
                break
        range_match = _TIME_RANGE_PATTERN.search(line)
        if range_match:
            login = validate_time_format(range_match.group(1).strip())
            logout = validate_time_format(range_match.group(2).strip())
            if login and logout:
                hours = _extract_duration(line) or calculate_hours(login, logout)
                entries.append({"date": current_date, "login": login, "logout": logout, "hours": hours})
                continue
        times_on_line = _STANDALONE_TIME.findall(line)
        if len(times_on_line) >= 2:
            login = validate_time_format(times_on_line[0].strip())
            logout = validate_time_format(times_on_line[1].strip())
            if login and logout:
                hours = _extract_duration(line) or calculate_hours(login, logout)
                entries.append({"date": current_date, "login": login, "logout": logout, "hours": hours})

    if not entries:
        all_times = _STANDALONE_TIME.findall(text)
        validated = [validate_time_format(t.strip()) for t in all_times if validate_time_format(t.strip())]
        for i in range(0, len(validated) - 1, 2):
            entries.append({
                "date": None,
                "login": validated[i],
                "logout": validated[i + 1],
                "hours": calculate_hours(validated[i], validated[i + 1]),
            })

    return {"entries": entries}


# ---------------------------------------------------------------------------
# Post-processing & Confidence Score
# ---------------------------------------------------------------------------

def _post_process(result: dict, source: str) -> dict:
    employee_name = result.get("employee_name", "Unknown")
    entries = result.get("entries", [])
    cleaned = []
    for entry in entries:
        date = entry.get("date")
        login = entry.get("login")
        logout = entry.get("logout")
        hours = entry.get("hours")

        if isinstance(login, str):
            if login.strip().lower() in ["null", "none", "na", "n/a", "-", ""]:
                login = None
            else:
                login = validate_time_format(login) or login
        if isinstance(logout, str):
            if logout.strip().lower() in ["null", "none", "na", "n/a", "-", ""]:
                logout = None
            else:
                logout = validate_time_format(logout) or logout
        if isinstance(date, str):
            date = normalise_date(date)
        if hours is None and login and logout:
            hours = calculate_hours(login, logout)
        if isinstance(hours, (int, float)):
            hours = round(float(hours), 2)
        elif isinstance(hours, str):
            try:
                hours = round(float(hours), 2)
            except ValueError:
                hours = 0.0

        has_time = bool(login and logout)
        has_partial_time = bool(login or logout)
        has_hours = hours is not None and float(hours) > 0

        if date and has_time and has_hours:
            confidence = "high"
        elif has_partial_time or has_hours:
            confidence = "medium"
        else:
            confidence = "low"

        cleaned.append({
            "date": date,
            "login": login,
            "logout": logout,
            "hours": hours,
            "confidence": confidence,
        })

    return {
        "employee_name": employee_name,
        "entries": cleaned,
        "total_entries": len(cleaned),
        "parse_source": source,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_timesheet_image(image_path: str, ocr_text: str = "") -> dict:
    """
    Main entry point for parsing a timesheet from an image file.

    Priority:
      1. Gemini Vision (image → Gemini 2.5 Flash directly)  [most accurate]
      2. Gemini Text  (OCR text → Gemini 2.5 Flash)         [accurate, needs OCR first]
      3. Regex        (OCR text → rule-based parser)         [last resort]
    """
    # --- Primary: Gemini Vision ---
    vision_result = _try_gemini_vision(image_path)
    if vision_result and vision_result.get("entries"):
        print("[Parser] Source: Gemini Vision (High Confidence)")
        return _post_process(vision_result, source="gemini-vision")

    # --- Fallback A: Gemini Text (if OCR text is available) ---
    if ocr_text:
        text = clean_ocr_text(ocr_text)
        gemini_text_result = _try_gemini_text(text)
        if gemini_text_result and gemini_text_result.get("entries"):
            print("[Parser] Source: Gemini Text (Reasonable Confidence)")
            return _post_process(gemini_text_result, source="gemini-text")

    # --- Fallback B: Regex ---
    print("[Parser] Source: Local Regex (Basic Recognition)")
    text = clean_ocr_text(ocr_text) if ocr_text else ""
    if not text:
        return {
            "employee_name": "Unknown",
            "entries": [],
            "total_entries": 0,
            "parse_source": "none",
            "error": "No text or image data available"
        }
    regex_result = _regex_parse(text)
    return _post_process(regex_result, source="regex")


