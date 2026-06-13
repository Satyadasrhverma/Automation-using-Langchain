# HR Offer Letter Generator

An AI-powered web app that extracts candidate data from Excel or PDF files, generates personalized job offer letters using **Groq (LLaMA 3.3 70B)**, produces a formatted PDF, and sends it directly via **Gmail OAuth** — all from a clean browser UI.

---

## Features

- **File upload** — drag & drop or browse; supports `.xlsx`, `.xls`, and `.pdf` (up to 16 MB)
- **Smart extraction** — auto-detects name, email, phone, and skills columns in Excel; falls back to table + raw-text parsing for PDFs
- **AI offer letters** — Groq generates a formal, personalized email draft tailored to the candidate's skills and the job details you provide
- **PDF generation** — a branded, print-ready offer letter PDF is created alongside the email
- **Gmail integration** — connect your Google account with OAuth 2.0 and send the email + PDF attachment in one click
- **CSV export** — download all extracted candidates as a spreadsheet
- **Live search** — filter candidates by name, email, phone, or skill in real time
- **Responsive UI** — works on desktop and mobile

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask |
| AI | Groq API — LLaMA 3.3 70B Versatile |
| PDF | fpdf2 |
| Data extraction | pandas, pdfplumber |
| Email | Gmail API via `google-auth-oauthlib` |
| Frontend | Vanilla HTML / CSS / JavaScript |

---

## Project Structure

```
automation/
├── app.py                  # Flask app — routes, file parsing, orchestration
├── generators/
│   ├── offer.py            # Groq prompt, email draft + PDF builder
│   └── mailer.py           # Gmail OAuth flow and send logic
├── templates/
│   └── index.html          # Single-page frontend
├── .env.example            # Environment variable template
└── .gitignore
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10 or newer
- A [Groq API key](https://console.groq.com) (free tier available)
- A Google Cloud project with the **Gmail API** enabled and an **OAuth 2.0 Web Client** credential

### 2. Clone & install dependencies

```bash
git clone https://github.com/Satyadasrhverma/Automation-using-Langchain.git
cd Automation-using-Langchain
pip install flask groq python-dotenv pandas pdfplumber fpdf2 openpyxl \
            google-auth google-auth-oauthlib google-api-python-client
```

### 3. Set up Google OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client ID** → choose **Web application**
3. Under **Authorized redirect URIs** add:
   ```
   http://localhost:5000/auth/callback
   ```
4. Copy the **Client ID** and **Client Secret**
5. Enable the **Gmail API** under **APIs & Services** → **Enabled APIs**

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback
FLASK_SECRET_KEY=some_random_secret_string
```

### 5. Run the app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## Usage

### Step 1 — Upload a file
Drag and drop (or click to browse) an Excel or PDF file containing candidate data. The app auto-detects columns — no fixed format required as long as email addresses are present.

### Step 2 — Review extracted candidates
Extracted records are shown in a searchable table with name, email, phone, and skills. You can export the full list as CSV at any time.

### Step 3 — Generate an offer letter
Click **Generate Offer** next to any candidate. Fill in the job details (company, position, department, start date, salary) and click **Generate Offer Letter**.

The AI produces:
- A formal email draft (editable before sending)
- A branded PDF offer letter (downloadable immediately)

### Step 4 — Send via Gmail *(optional)*
Click the **Gmail: Not connected** badge in the navbar to authorise your Google account. Once connected, click **Send via Gmail** to deliver the email with the PDF attached directly from your account.

---

## Input File Format

### Excel (.xlsx / .xls)
No strict template required. The app scans column headers for common keywords:

| Data | Detected keywords |
|---|---|
| Email | `email`, `e-mail`, `mail` |
| Name | `name`, `full name`, `candidate`, `applicant` |
| Phone | `phone`, `mobile`, `contact`, `tel` |
| Skills | `skill`, `skills`, `expertise`, `technology`, `tech` |

If a column is not found the app falls back to scanning all cell values.

### PDF
The app first attempts table extraction (for structured PDFs), then falls back to raw text scanning. Any email address found acts as an anchor — phone and skill context is extracted from the surrounding lines.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for LLaMA inference |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth 2.0 client secret |
| `GOOGLE_REDIRECT_URI` | Yes | Must match the URI registered in Google Cloud |
| `FLASK_SECRET_KEY` | Yes | Secret key for Flask session security |

---

## Security Notes

- `.env` and `token.json` are excluded from version control via `.gitignore` — **never commit them**
- `token.json` is created automatically after Gmail OAuth and stores your refresh token locally
- All uploaded files are deleted from disk immediately after parsing
- The Gmail scope requested is limited to `gmail.send` only — the app cannot read your emails

---

## License

MIT
