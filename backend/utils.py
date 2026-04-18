"""
utils.py — Helper utilities for the AI Timesheet Automation System.
Handles time validation, text normalization, and hour calculations.
"""

import re
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Text Cleaning
# ---------------------------------------------------------------------------

def clean_ocr_text(text: str) -> str:
    """
    Remove common OCR noise from extracted text.
    - Strips odd characters / symbols unlikely to appear in timesheets
    - Normalises whitespace and line breaks
    - Fixes common OCR misreads (O→0, l→1, etc.) only in time-like contexts
    """
    if not text:
        return ""

    # Normalize various dash-like characters to a standard hyphen
    text = re.sub(r"[–—]", "-", text)

    # Remove non-printable / control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Collapse multiple spaces into one
    text = re.sub(r"[ \t]+", " ", text)

    # Normalise multiple blank lines into a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Fix OCR confusion: capital-O where digit 0 is expected in HH:MM patterns
    text = re.sub(r"(?<!\w)O(\d):", r"0\1:", text)
    text = re.sub(r":O(?!\w)", ":0", text)

    # Fix lowercase-L where digit 1 is expected (e.g. "l0:30" → "10:30")
    text = re.sub(r"(?<!\w)l(\d):", r"1\1:", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Time Validation & Normalisation
# ---------------------------------------------------------------------------




def validate_time_format(time_str: str) -> Optional[str]:
    """
    Try to parse *time_str* and return a normalised 'HH:MM' (24-hour) string.
    Returns None if parsing fails.
    """
    if not time_str:
        return None

    time_str = time_str.strip()

    # Attempt 12-hour parse
    for pattern, fmt in [
        (r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)", "%I:%M %p"),
    ]:
        m = re.fullmatch(pattern, time_str, re.IGNORECASE)
        if m:
            try:
                dt = datetime.strptime(time_str.upper(), "%I:%M %p")
                return dt.strftime("%H:%M")
            except ValueError:
                pass

    # Attempt 24-hour parse
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", time_str)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None


def parse_time_to_dt(time_str: str) -> Optional[datetime]:
    """
    Convert a normalised 'HH:MM' string to a datetime object (today's date).
    """
    try:
        return datetime.strptime(time_str, "%H:%M")
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Hour Calculation
# ---------------------------------------------------------------------------

def calculate_hours(login: str, logout: str) -> Optional[float]:
    """
    Calculate the difference between login and logout times in hours.
    Assumes logout is after login (handles overnight shifts).
    Returns a float rounded to 2 decimal places, or None on bad input.
    """
    login_dt = parse_time_to_dt(login)
    logout_dt = parse_time_to_dt(logout)

    if login_dt is None or logout_dt is None:
        return None

    # Handle overnight shift (e.g., login=22:00, logout=06:00)
    if logout_dt < login_dt:
        logout_dt += timedelta(days=1)

    delta = logout_dt - login_dt
    hours = delta.total_seconds() / 3600
    return round(hours, 2)


# ---------------------------------------------------------------------------
# Date Normalisation
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d",   # 2024-01-15
    "%d/%m/%Y",   # 15/01/2024
    "%m/%d/%Y",   # 01/15/2024
    "%d-%m-%Y",   # 15-01-2024
    "%B %d, %Y",  # January 15, 2024
    "%b %d, %Y",  # Jan 15, 2024
    "%d %B %Y",   # 15 January 2024
    "%d %b %Y",   # 15 Jan 2024
    "%A, %B %d",  # Monday, January 15
    "%A %d %B",   # Monday 15 January
    "%b %d",      # Jan 15
]




def normalise_date(date_str: str) -> str:
    """
    Try to parse *date_str* into 'YYYY-MM-DD'.
    Falls back to the original string if no format matches.
    """
    if not date_str:
        return date_str

    date_str = date_str.strip()
    current_year = datetime.now().year

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # If year is missing, assume current year
            if dt.year == 1900:
                dt = dt.replace(year=current_year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str  # return as-is if nothing matched
