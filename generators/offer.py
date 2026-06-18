import base64
import os
from datetime import datetime
from io import BytesIO

from jinja2 import BaseLoader, Environment
from xhtml2pdf import pisa

COMPANY_NAME  = "Vorldx Adgorithm Lab"
_ASSETS_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
_PDF_TEMPLATE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates", "offer_letter_pdf.html"))


# ── Unified LLM caller (Groq / OpenAI / Claude) ───────────────────────────────

def _llm(prompt: str, max_tokens: int, provider: str, api_key: str) -> str:
    if provider == "openai":
        from openai import OpenAI
        r = OpenAI(api_key=api_key).chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content.strip()

    if provider == "claude":
        from anthropic import Anthropic
        r = Anthropic(api_key=api_key).messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text.strip()

    # default: groq
    from groq import Groq
    r = Groq(api_key=api_key).chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _logo_data_uri() -> str:
    if not os.path.isdir(_ASSETS_DIR):
        return ""
    for fname in os.listdir(_ASSETS_DIR):
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext in ("png", "jpg", "jpeg", "gif", "webp"):
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            with open(os.path.join(_ASSETS_DIR, fname), "rb") as fh:
                return f"data:{mime};base64,{base64.b64encode(fh.read()).decode()}"
    return ""


def _render_template(template_str: str, **ctx) -> str:
    return Environment(loader=BaseLoader(), autoescape=True).from_string(template_str).render(**ctx)


def _html_to_pdf(html: str) -> bytes:
    buf = BytesIO()
    pisa.CreatePDF(html, dest=buf)
    return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────

def generate_offer_letter(
    record: dict,
    job_details: dict,
    provider: str = "groq",
    api_key: str = "",
) -> tuple[str, str]:
    name       = record.get("name", "Candidate")
    skills     = record.get("skills", "—")
    company    = job_details.get("company", COMPANY_NAME)
    position   = job_details.get("position", "the offered position")
    department = job_details.get("department", "")
    start_date = job_details.get("start_date", "To be confirmed")
    salary     = job_details.get("salary", "")

    skills_text     = skills if skills != "—" else "your relevant qualifications"
    first_name      = name.split()[0] if name else "Candidate"
    employment_type = "Internship" if "intern" in position.lower() else "Full-Time"
    dept_display    = f", {department} Department" if department else ""
    salary_clause   = (
        f"The stipend/compensation for this position is {salary}, payable on a monthly basis."
        if salary else
        "The details of your compensation package will be communicated to you prior to your joining date."
    )

    # Fixed email template — consistent for all candidates
    email_text = f"""Subject: Official Offer of Employment - {position} | {company}

Dear {first_name},

We are pleased to offer you the position of {position}{dept_display} at {company} as a {employment_type}, commencing {start_date}. {salary_clause}

Please find the attached PDF Offer Letter containing the complete terms and conditions of your engagement. Kindly review and confirm your acceptance within 3 business days by replying to this email. For any queries, reach us at hr@vorldxadgorithmlab.com.

We look forward to welcoming you to the team. Congratulations!

Warm regards,
Human Resources Department
{company}
hr@vorldxadgorithmlab.com"""

    # AI generates only the duties line for the PDF
    duties_prompt = (
        f"Write ONE concise sentence (max 30 words) describing the core responsibilities "
        f"for a {position} role at a digital marketing and technology company. "
        f"Relevant skills: {skills_text}. "
        "Start with a strong action verb. Return only the sentence, no preamble."
    )
    duties_text = _llm(duties_prompt, 80, provider, api_key).rstrip(".")

    pdf_bytes = _build_pdf(
        name, first_name, record.get("email", ""),
        company, position, department, start_date, salary,
        duties_text, employment_type,
    )
    return email_text, base64.b64encode(pdf_bytes).decode()


def _build_pdf(
    name, first_name, email,
    company, position, department, start_date, salary,
    duties_text, employment_type,
) -> bytes:
    with open(_PDF_TEMPLATE, encoding="utf-8") as fh:
        template_str = fh.read()

    html = _render_template(
        template_str,
        name=name,
        first_name=first_name,
        email=email,
        company=company,
        position=position,
        dept_text=f" in the {department} Department" if department else "",
        employment_type=employment_type,
        start_date=start_date,
        salary=salary,
        duties_text=duties_text,
        date=datetime.today().strftime("%m/%d/%Y"),
        logo_src=_logo_data_uri(),
    )
    return _html_to_pdf(html)
