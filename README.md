# AI Timesheet Automation System

A full-stack web application that extracts structured work-hour data from timesheet screenshots using OCR (EasyOCR) and AI parsing (Google Gemini 2.5 Flash with regex fallback).

---

## 📁 Project Structure

```
OCR Project/
├── backend/
│   ├── main.py          # FastAPI app & REST endpoints
│   ├── ocr.py           # EasyOCR image preprocessing & extraction
│   ├── parser.py        # Gemini 2.5 Flash AI + regex fallback parser
│   ├── utils.py         # Time validation, cleaning, hour calculation
│   └── requirements.txt # Python dependencies
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── App.jsx
        ├── App.css
        ├── index.css
        └── components/
            ├── UploadZone.jsx    # Drag-and-drop file upload
            ├── ImagePreview.jsx  # Thumbnail preview
            ├── ProcessButton.jsx # Submit with loading state
            └── ResultDisplay.jsx # Structured JSON output
```

---

## 🚀 Setup & Running

### Prerequisites
- Python 3.9+
- Node.js 18+ 

### Backend

```powershell
cd backend
# Install dependencies:
python -m pip install -r requirements.txt

# Create a .env file from the template:
copy .env.example .env
# Open .env and fill in your keys (see Environment Variables section below)

# Start backend server
python -m uvicorn main:app --reload --port 8000
```

The backend API will be at: **http://localhost:8000**
Interactive docs (Swagger): **http://localhost:8000/docs**

### Frontend

Open a **second terminal**:

```powershell
cd frontend
npm install
npm run dev
```

The app will be at: **http://localhost:5173**

---

## 🔑 Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the following:

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key — get one at [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `TIMESHEET_API_URL` | Your external timesheet database API endpoint |
| `TIMESHEET_API_KEY` | API key for authenticating with the external timesheet API |

> **Note:** The `/submit-timesheet` endpoint is disabled if `TIMESHEET_API_URL` and `TIMESHEET_API_KEY` are not set. The OCR and parsing features still work fully without them.

---

## ⚙️ API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/upload-timesheet` | Upload image → OCR → AI parse → return structured JSON |
| `POST` | `/submit-timesheet` | Forward parsed timesheet data to an external database API |

### `POST /upload-timesheet`

Accepts a timesheet image and returns structured work-hour data.

**Response:**
```json
{
  "success": true,
  "filename": "clockify_screenshot.png",
  "raw_text": "...",
  "result": {
    "employee_name": "Jane Smith",
    "entries": [
      {
        "date": "2024-01-15",
        "login": "09:00",
        "logout": "17:30",
        "hours": 8.5,
        "confidence": "high"
      }
    ],
    "total_entries": 1,
    "parse_source": "gemini-vision"
  }
}
```

### `POST /submit-timesheet`

Forwards the parsed timesheet entries to an external database API. This endpoint is designed to integrate with a company's own timesheet management backend.

- Requires `TIMESHEET_API_URL` and `TIMESHEET_API_KEY` to be set in `.env`
- Skips entries with missing or zero hours before submitting
- Includes **retry logic** (3 attempts) to handle cold-start delays from hosted APIs (e.g. Render free tier)
- Sends data as JSON with `x-api-key` header authentication

**Request body:**
```json
{
  "employee_name": "Jane Smith",
  "entries": [
    {
      "date": "2024-01-15",
      "login": "09:00",
      "logout": "17:30",
      "hours": 8.5,
      "confidence": "high"
    }
  ],
  "total_entries": 1,
  "parse_source": "gemini-vision"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Timesheet data uploaded to database successfully.",
  "api_response": { ... }
}
```

---

## 🧠 How It Works

1. **Upload**: User drops a timesheet screenshot (PNG/JPEG/WEBP/BMP/TIFF)
2. **Preprocess**: OpenCV converts to grayscale + adaptive threshold
3. **OCR**: EasyOCR extracts raw text (downloads ~100MB model on first run — used as fallback only)
4. **AI Parse**: Google Gemini 2.5 Flash attempts to extract structured JSON directly from the image
5. **Fallback**: If AI vision fails, OCR text is passed back to Gemini; if that also fails, regex patterns detect dates, time ranges, and durations
6. **Validate**: Times normalised to HH:MM, dates to YYYY-MM-DD, hours calculated
7. **Display**: Frontend shows entry cards + raw JSON + OCR text
8. **Submit** *(optional)*: User clicks "Submit" to forward parsed entries to a configured external timesheet database API

---

## 📝 Supported Timesheet Formats

- `9:00 AM - 5:30 PM` (12-hour with AM/PM)
- `09:00 - 17:30` (24-hour range)
- `8h 30m` / `8.5 hrs` (duration)
- Dates: `2024-01-15`, `15/01/2024`, `Jan 15, 2024`, `Monday 15 January`
- Multi-day timesheets (multiple entries per image)

---

## ⚠️ First-Run Notes

- **EasyOCR** downloads a ~100MB English language model on first use
- Processing the first image may take 10-30 seconds if it needs to download the OCR model. Subsequent ones are faster.
