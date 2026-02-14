# Timetable Parser API (pdf_extractor)

A small FastAPI application that extracts a timetable from a PDF file. The API accepts a PDF via `multipart/form-data`, parses a table using pdfplumber, and returns structured JSON (weekdays → hours → entries).

## Features

- Upload a timetable as PDF (`/upload`)
- Table extraction using pdfplumber (line-based detection)
- Output grouped by weekday and hour, including subject, teacher, room, and specialization/group
- CORS enabled for `http://localhost:3000` by default (for a local frontend)

## Requirements

- Python 3.13 (or compatible 3.x)
- Windows PowerShell or another terminal (commands below are PowerShell-friendly)
- Optional: Docker

## Quickstart

### Option A: Local run (pip/venv)

```powershell
# 1) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1 # or the right script for your terminal

# 2) (Optional) Install pip-tools to manage/updgrade requirements
python -m pip install pip-tools

# 3) Generate or update requirements.txt from top-level requirements.in
# - First time or selective:    pip-compile requirements.in
# - Upgrade all packages:       pip-compile -o requirements.txt --upgrade requirements.in --strip-extras

# 4) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5) Start the API (default: http://127.0.0.1:8080)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Interactive docs:

- Swagger UI: http://127.0.0.1:8080/docs
- ReDoc: http://127.0.0.1:8080/redoc

Want LAN access (e.g., from another device)? Start with `--host 0.0.0.0` and use your machine’s IP, e.g., `http://192.168.x.x:8080`.

Note: The repo nutzt `requirements.txt` als Quelle für Dependencies. Verwalte Updates bequem mit pip-tools über `requirements.in` und `pip-compile`.

### Option B: Docker

The provided `Dockerfile` exposes port `8080` in the container.

```powershell
# Build the image (from the project root)
docker build -t pdf-extractor .

# Run the container and map the port
docker run --name timetable-pdf-extractor -p 8080:8080 pdf-extractor
```

The API will be available at: http://127.0.0.1:8080

### Option C: Google Cloud Run

The project can also be deployed on Google Cloud Run. You can find concise step-by-step instructions here:

https://dev.to/0xnari/deploying-fastapi-app-with-google-cloud-run-13f3

Note: The provided `Dockerfile` already listens on port `8080`, which is compatible with Cloud Run.

## API

### POST /upload

- Description: Accepts a PDF file and extracts the timetable.
- Content-Type: `multipart/form-data`
- Field name: `file` (must be a PDF, `application/pdf`)

Example response (truncated):

```json
{
	"class": "10A",
	"timetable": {
		"Montag": {
			"1": [
				{"subject": "MATH", "teacher": "MM", "room": "E201", "specialization": 1}
			],
			"2": [ /* ... */ ]
		},
		"Dienstag": { /* ... */ }
	}
}
```

Entry fields:

- `subject`: Subject
- `teacher`: Teacher
- `room`: Room
- `specialization`: Grouping
	- 1 = whole class or merged groups
	- 2 = group A
	- 3 = group B

Detection notes: The PDF should contain a clearly detectable table. The app uses pdfplumber with line strategies (`vertical_strategy`/`horizontal_strategy` = `lines`). Non-standard layouts may be harder to parse reliably.

## CORS notes

In `app/main.py`, CORS is enabled for the origin `http://localhost:3000`—ideal for a local frontend. If your frontend runs at a different address/port, add that origin to the `origins` list.

- The origin is the page your browser script runs from (e.g., `http://localhost:3000`).
- The backend URL you call (e.g., `http://127.0.0.1:8080/upload` or `http://192.168.x.x:8080/upload`) does not change the origin.

## Troubleshooting

- 400 Bad Request:
	- Common: Request is not `multipart/form-data` or field name is not `file`.
	- File is not a PDF, or the table cannot be detected (error: "No table found in the PDF.").
- 415 Unsupported Media Type:
	- Wrong Content-Type—use `multipart/form-data` with a file field.
- 500 Internal Server Error:
	- Unexpected error during PDF processing. Check server logs and try a different PDF.
- CORS errors:
	- Ensure `http://localhost:3000` (or your actual frontend origin) is in `allow_origins`. Restart the server after changes.

## Project structure (excerpt)

```
.
├─ app/
│  └─ main.py            # FastAPI app (/upload endpoint, CORS)
├─ requirements.txt      # Python dependencies (pip)
├─ Dockerfile            # Docker image (port 8080)
└─ README.md             # This file
```

## License

MIT License
