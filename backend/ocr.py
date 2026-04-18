"""
ocr.py — OCR layer for the AI Timesheet Automation System.
Handles image preprocessing (grayscale, threshold) and text extraction via EasyOCR.
"""

import cv2
import numpy as np
import easyocr
from PIL import Image

# ---------------------------------------------------------------------------
# EasyOCR reader — initialised once at module level to avoid reload overhead.
# Supports English; set gpu=True if CUDA is available.
# ---------------------------------------------------------------------------
_reader: easyocr.Reader | None = None


def _get_reader() -> easyocr.Reader:
    """Lazy-load the EasyOCR reader (downloads model on first call)."""
    global _reader
    if _reader is None:
        print("[OCR] Initialising EasyOCR reader (may download model on first run)…")
        _reader = easyocr.Reader(["en"], gpu=False)
        print("[OCR] EasyOCR reader ready.")
    return _reader


def warmup_reader() -> None:
    """Preload EasyOCR model during app startup."""
    _get_reader()


# ---------------------------------------------------------------------------
# Image Preprocessing
# ---------------------------------------------------------------------------

def preprocess_image(image_path: str) -> np.ndarray:
    """
    Load an image and apply preprocessing to maximise OCR accuracy:
    1. Convert to grayscale
    2. Upscale if small (minimum 1200px width)
    3. Apply adaptive thresholding to binarize the image
    4. Denoise with a mild Gaussian blur before thresholding

    Returns a preprocessed NumPy array (grayscale).
    """
    # Load with OpenCV
    img = cv2.imread(image_path)
    if img is None:
        # Fallback: try loading via Pillow (handles more formats)
        pil_img = Image.open(image_path).convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Upscale if the image is too small (improves OCR on small text)
    height, width = gray.shape
    if width < 1200:
        scale = 1200 / width
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 3. Mild Gaussian blur to reduce noise before binarization
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. Adaptive threshold — handles uneven lighting across the image
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )

    return binary


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def extract_text(image_path: str) -> str:
    """
    Run EasyOCR on the (preprocessed) image and return a single string
    with all detected text joined by newlines.

    The results are sorted top-to-bottom, left-to-right to preserve the
    natural reading order of tabular timesheet data.
    """
    reader = _get_reader()

    preprocessed = preprocess_image(image_path)

    # EasyOCR accepts a NumPy array directly
    results = reader.readtext(preprocessed, detail=1, paragraph=False)

    # Each result: (bounding_box, text, confidence)
    # Sort by vertical position (top of bounding box), then horizontal
    def sort_key(item):
        bbox = item[0]  # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
        top_y = min(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        return (top_y, left_x)

    results.sort(key=sort_key)

    # Filter out very low-confidence detections that are likely noise
    MIN_CONFIDENCE = 0.3
    lines = [text for (_, text, conf) in results if conf >= MIN_CONFIDENCE]

    raw_text = "\n".join(lines)
    print(f"[OCR] Extracted {len(lines)} text segments.")
    return raw_text
