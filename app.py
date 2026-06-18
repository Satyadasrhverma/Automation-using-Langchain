import base64
import os
import re
import pandas as pd
import pdfplumber
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify, redirect, session, send_from_directory
from werkzeug.utils import secure_filename
from generators.offer import generate_offer_letter
from generators.mailer import build_flow, creds_from_json, send_offer_email

load_dotenv(override=True)

# Allow HTTP only in local dev; Vercel always uses HTTPS
if os.getenv("VERCEL") != "1":
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("VERCEL") == "1"

# Vercel only allows writes to /tmp
_upload_base = "/tmp" if os.getenv("VERCEL") == "1" else "."
app.config["UPLOAD_FOLDER"] = os.path.join(_upload_base, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/callback")

ALLOWED_EXTENSIONS = {"xlsx", "xls", "pdf"}

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
SKILL_SECTION = re.compile(
    r"(?:skills?|expertise|technologies|tech\s*stack)[:\s]*(.+?)(?:\n\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_fallback_provider = "groq"
_fallback_api_key  = os.getenv("GROQ_API_KEY", "")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def looks_like_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 15


def find_column(columns, keywords):
    for col in columns:
        if any(kw in str(col).lower() for kw in keywords):
            return col
    return None


def name_from_email(email: str) -> str:
    local = email.split("@")[0]
    parts = re.split(r"[._\-]", local)
    return " ".join(p.capitalize() for p in parts if p)


# ── Excel extraction ──────────────────────────────────────────────────────────

def extract_from_excel(filepath: str) -> list[dict]:
    df = pd.read_excel(filepath)
    df.columns = [str(c).strip() for c in df.columns]
    cols = df.columns.tolist()

    email_col = find_column(cols, ["email", "e-mail", "mail"])
    phone_col = find_column(cols, ["phone", "mobile", "contact", "tel", "number"])
    skill_col = find_column(cols, ["skill", "skills", "expertise", "technology", "tech"])
    name_col  = find_column(cols, ["name", "full name", "fullname", "fname", "candidate", "person", "applicant"])

    results = []
    for _, row in df.iterrows():
        email = phone = skills = name = None

        if email_col and pd.notna(row[email_col]):
            m = EMAIL_PATTERN.search(str(row[email_col]))
            if m:
                email = m.group()
        if not email:
            for col in cols:
                m = EMAIL_PATTERN.search(str(row[col]) if pd.notna(row[col]) else "")
                if m:
                    email = m.group()
                    break
        if not email:
            continue

        if phone_col and pd.notna(row[phone_col]):
            candidate = str(row[phone_col]).strip()
            if looks_like_phone(candidate):
                phone = candidate
        if not phone:
            for col in cols:
                if col == email_col:
                    continue
                m = PHONE_PATTERN.search(str(row[col]) if pd.notna(row[col]) else "")
                if m and looks_like_phone(m.group()):
                    phone = m.group().strip()
                    break

        if skill_col and pd.notna(row[skill_col]):
            skills = str(row[skill_col]).strip()

        if name_col and pd.notna(row[name_col]):
            name = str(row[name_col]).strip()
        if not name:
            name = name_from_email(email)

        results.append({"name": name, "email": email, "phone": phone or "—", "skills": skills or "—"})
    return results


# ── PDF extraction ────────────────────────────────────────────────────────────

def _context_around(lines: list[str], idx: int, window: int = 4) -> str:
    start = max(0, idx - window)
    end   = min(len(lines), idx + window + 1)
    return " ".join(lines[start:end])


def extract_from_pdf(filepath: str) -> list[dict]:
    results = []
    seen_emails: set[str] = set()

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:

            # ── Try table extraction first ──
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                headers = [str(h).strip().lower() if h else "" for h in table[0]]
                email_idx = next((i for i, h in enumerate(headers)
                                  if any(k in h for k in ["email", "e-mail", "mail"])), None)
                phone_idx = next((i for i, h in enumerate(headers)
                                  if any(k in h for k in ["phone", "mobile", "contact", "tel"])), None)
                skill_idx = next((i for i, h in enumerate(headers)
                                  if any(k in h for k in ["skill", "expertise", "tech"])), None)
                name_idx  = next((i for i, h in enumerate(headers)
                                  if any(k in h for k in ["name", "full name", "fullname", "fname", "candidate", "person"])), None)

                for row in table[1:]:
                    if not row:
                        continue
                    row_text = " ".join(str(c) for c in row if c)

                    if email_idx is not None and email_idx < len(row) and row[email_idx]:
                        m = EMAIL_PATTERN.search(str(row[email_idx]))
                        email = m.group() if m else None
                    else:
                        m = EMAIL_PATTERN.search(row_text)
                        email = m.group() if m else None

                    if not email or email in seen_emails:
                        continue
                    seen_emails.add(email)

                    phone = None
                    if phone_idx is not None and phone_idx < len(row) and row[phone_idx]:
                        candidate = str(row[phone_idx]).strip()
                        if looks_like_phone(candidate):
                            phone = candidate
                    if not phone:
                        pm = PHONE_PATTERN.search(row_text)
                        if pm and looks_like_phone(pm.group()):
                            phone = pm.group().strip()

                    skills = None
                    if skill_idx is not None and skill_idx < len(row) and row[skill_idx]:
                        skills = str(row[skill_idx]).strip()

                    name = None
                    if name_idx is not None and name_idx < len(row) and row[name_idx]:
                        name = str(row[name_idx]).strip()
                    if not name:
                        name = name_from_email(email)

                    results.append({"name": name, "email": email, "phone": phone or "—", "skills": skills or "—"})

            # ── Fall back to raw text extraction ──
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            skills_block = ""
            sm = SKILL_SECTION.search(text)
            if sm:
                raw = sm.group(1)
                skills_block = ", ".join(
                    t.strip() for t in re.split(r"[,\n|•●\-–]", raw) if t.strip()
                )

            for i, line in enumerate(lines):
                m = EMAIL_PATTERN.search(line)
                if not m:
                    continue
                email = m.group()
                if email in seen_emails:
                    continue
                seen_emails.add(email)

                context = _context_around(lines, i)

                phone = None
                pm = PHONE_PATTERN.search(context)
                if pm and looks_like_phone(pm.group()):
                    phone = pm.group().strip()

                results.append({
                    "name": name_from_email(email),
                    "email": email,
                    "phone": phone or "—",
                    "skills": skills_block or "—",
                })

    return results


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/logo")
def serve_logo():
    assets = os.path.join(os.path.dirname(__file__), "assets")
    for fname in os.listdir(assets):
        if fname.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return send_from_directory(assets, fname)
    return "", 404

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only .xlsx, .xls, and .pdf files are allowed"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        ext = filename.rsplit(".", 1)[1].lower()
        if ext == "pdf":
            records = extract_from_pdf(filepath)
        else:
            records = extract_from_excel(filepath)
    except Exception as exc:
        return jsonify({"error": f"Failed to parse file: {exc}"}), 500
    finally:
        os.remove(filepath)

    return jsonify({"count": len(records), "data": records})


@app.route("/generate-offer", methods=["POST"])
def generate_offer():
    body = request.get_json(silent=True) or {}
    record      = body.get("record")
    job_details = body.get("job_details", {})
    if not record:
        return jsonify({"error": "Missing record"}), 400

    provider = body.get("provider", _fallback_provider)
    api_key  = body.get("api_key",  _fallback_api_key)
    if not api_key:
        return jsonify({"error": "No API key provided. Please set your API key first."}), 400

    try:
        email_draft, pdf_base64 = generate_offer_letter(record, job_details, provider, api_key)
    except Exception as exc:
        return jsonify({"error": f"Generation error: {exc}"}), 500

    return jsonify({"email_draft": email_draft, "pdf_base64": pdf_base64})


# ── Gmail OAuth (session-based — each user has their own token) ───────────────

@app.route("/auth/status")
def auth_status():
    authorized = creds_from_json(session.get("gmail_creds")) is not None
    return jsonify({"authorized": authorized})


@app.route("/auth/google")
def auth_google():
    flow = build_flow(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)
    auth_url, state = flow.authorization_url(access_type="offline", prompt="select_account consent")
    session["oauth_code_verifier"] = flow.code_verifier
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/auth/callback")
def auth_callback():
    flow = build_flow(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)
    flow.code_verifier = session.pop("oauth_code_verifier", None)
    flow.fetch_token(authorization_response=request.url)
    session["gmail_creds"] = flow.credentials.to_json()
    return redirect("/?gmail=connected")


@app.route("/auth/revoke", methods=["POST"])
def auth_revoke():
    session.pop("gmail_creds", None)
    return jsonify({"success": True})


# ── Send email ────────────────────────────────────────────────────────────────

@app.route("/send-email", methods=["POST"])
def send_email_route():
    body           = request.get_json(silent=True) or {}
    to_email       = body.get("to_email", "")
    email_draft    = body.get("email_draft", "")
    pdf_base64     = body.get("pdf_base64", "")
    candidate_name = body.get("candidate_name", "candidate")

    if not to_email:
        return jsonify({"error": "Recipient email is required"}), 400

    # Parse Subject: line from draft
    lines   = email_draft.strip().splitlines()
    subject = "Job Offer Letter"
    body_text = email_draft
    if lines and lines[0].lower().startswith("subject:"):
        subject   = lines[0][8:].strip()
        body_text = "\n".join(lines[2:]).strip()

    pdf_bytes = base64.b64decode(pdf_base64) if pdf_base64 else None
    safe_name = candidate_name.replace(" ", "_")
    pdf_fname = f"offer_letter_{safe_name}.pdf"

    creds_json = session.get("gmail_creds")
    if not creds_json:
        return jsonify({"error": "Gmail not connected. Please connect your account first."}), 400

    try:
        ok, msg = send_offer_email(creds_json, to_email, subject, body_text, pdf_bytes, pdf_fname)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"error": msg}), 400


if __name__ == "__main__":
    app.run(debug=True)
