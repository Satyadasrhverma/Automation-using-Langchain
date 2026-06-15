import base64
import os
from datetime import datetime
from fpdf import FPDF, XPos, YPos

COMPANY_NAME    = "Vorldx Adgorithm Lab"
COMPANY_ADDRESS = "www.vorldxadgorithmlab.com"
LOGO_PATH       = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")


def generate_offer_letter(record: dict, job_details: dict, groq_client) -> tuple[str, str]:
    name       = record.get("name", "Candidate")
    skills     = record.get("skills", "—")
    company    = job_details.get("company", COMPANY_NAME)
    position   = job_details.get("position", "the offered position")
    department = job_details.get("department", "")
    start_date = job_details.get("start_date", "To be confirmed")
    salary     = job_details.get("salary", "")

    skills_text = skills if skills != "—" else "your relevant qualifications"
    first_name  = name.split()[0] if name else "Candidate"
    dept_line   = f" in the {department} Department" if department else ""
    salary_line = f"\n- Compensation: {salary}" if salary else ""

    # ── Email draft ──────────────────────────────────────────────────────────
    email_prompt = (
        f"Write a formal job offer letter email from the HR team at {company} to {name} "
        f"offering them the position of {position}{dept_line}.\n\n"
        f"Candidate skills: {skills_text}\n"
        f"Start date: {start_date}{salary_line}\n\n"
        "Requirements:\n"
        "- Subject line at the very top\n"
        "- Address by first name only\n"
        "- Professional, warm HR tone\n"
        "- Mention their skills as the reason for selection\n"
        "- Include: congratulations, position title, start date, next steps\n"
        "- Reference 'the attached PDF offer letter' for complete terms\n"
        "- End with HR team sign-off from Vorldx Adgorithm Lab\n"
        "- 3-4 paragraphs\n\n"
        "Format exactly as:\nSubject: <subject line>\n\n<email body>"
    )

    # ── Duties paragraph for PDF ─────────────────────────────────────────────
    duties_prompt = (
        f"Write ONE concise sentence (max 25 words) describing the key responsibilities "
        f"for a {position} role{dept_line} at a digital marketing and technology company, "
        f"relevant to someone with skills in {skills_text}. "
        "Start with an action verb. No preamble, just the sentence."
    )

    email_completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[{"role": "user", "content": email_prompt}],
    )
    duties_completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=80,
        messages=[{"role": "user", "content": duties_prompt}],
    )

    email_text  = email_completion.choices[0].message.content.strip()
    duties_text = duties_completion.choices[0].message.content.strip()

    pdf_bytes = _build_pdf(
        name, first_name, record.get("email", ""),
        company, position, department, start_date, salary, duties_text,
    )
    return email_text, base64.b64encode(pdf_bytes).decode()


def _build_pdf(
    name, first_name, email,
    company, position, department, start_date, salary, duties_text,
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    today = datetime.today().strftime("%m/%d/%Y")

    # ── Logo (top-right) ─────────────────────────────────────────────────────
    if os.path.exists(LOGO_PATH):
        pdf.image(LOGO_PATH, x=145, y=10, w=45)
        pdf.set_y(35)
    else:
        # Fallback: company name as text header if logo file not found
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 115, 190)
        pdf.cell(0, 10, company, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, COMPANY_ADDRESS, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        pdf.ln(4)

    # ── Date ─────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, today, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # ── Recipient block ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if email:
        pdf.cell(0, 6, email, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # ── Salutation ───────────────────────────────────────────────────────────
    pdf.cell(0, 6, f"Dear {first_name},", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    dept_text   = f" in the {department} Department" if department else ""
    salary_para = (
        f"The annual starting salary for this position is {salary}, to be paid on a monthly "
        "basis by direct deposit, starting on your first pay period."
        if salary else
        "Details regarding compensation and benefits will be discussed and confirmed prior to your start date."
    )

    # ── Paragraph 1 — Offer ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        f"We are pleased to offer you the full-time position of {position}{dept_text} at "
        f"{company} with a start date of {start_date}, contingent upon successful completion "
        "of a background verification and submission of required documentation (I-9 form, etc.). "
        f"You will be reporting directly to the HR Department at our office location. "
        "We believe your skills and experience are an excellent match for our company."
    )
    pdf.ln(5)

    # ── Paragraph 2 — Duties ────────────────────────────────────────────────
    pdf.multi_cell(0, 6,
        f"In this role, you will be required to {duties_text.rstrip('.')}."
    )
    pdf.ln(5)

    # ── Paragraph 3 — Salary ────────────────────────────────────────────────
    pdf.multi_cell(0, 6, salary_para)
    pdf.ln(5)

    # ── Paragraph 4 — At-will ───────────────────────────────────────────────
    pdf.multi_cell(0, 6,
        f"Your employment with {company} will be on an at-will basis, which means you and "
        "the company are free to terminate the employment relationship at any time for any reason. "
        "This letter is not a contract or guarantee of employment for a specific period of time."
    )
    pdf.ln(5)

    # ── Acceptance line ──────────────────────────────────────────────────────
    pdf.multi_cell(0, 6,
        "Please confirm your acceptance of this offer by signing and returning a copy of this "
        "letter by the acceptance deadline noted below. Should you have any questions, please "
        "do not hesitate to reach out to our HR team."
    )
    pdf.ln(5)
    pdf.cell(0, 6, "Acceptance Deadline: ___________________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # ── Sign-off ─────────────────────────────────────────────────────────────
    pdf.cell(0, 6, "Sincerely,", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(14)

    # Signature lines — two columns
    pdf.set_draw_color(60, 60, 60)
    pdf.set_line_width(0.3)
    sig_y = pdf.get_y()
    pdf.line(20, sig_y, 90, sig_y)
    pdf.line(110, sig_y, 180, sig_y)
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(90, 5, "Authorized Signature", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(0, 5, "Date")
    pdf.ln(7)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 5, "Human Resources Team", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, company, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # ── Candidate acceptance ─────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, "Candidate Acceptance", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 5,
        "I have read and understood the terms of this offer and accept the position as described.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(12)
    acc_y = pdf.get_y()
    pdf.line(20, acc_y, 90, acc_y)
    pdf.line(110, acc_y, 180, acc_y)
    pdf.ln(3)
    pdf.cell(90, 5, "Candidate Signature", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(0, 5, "Date")
    pdf.ln(10)

    # ── Footer ───────────────────────────────────────────────────────────────
    pdf.set_draw_color(30, 115, 190)
    pdf.set_line_width(0.5)
    footer_y = pdf.get_y()
    pdf.line(20, footer_y, 190, footer_y)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5,
        f"Confidential — {company} | Generated on {datetime.today().strftime('%B %d, %Y')}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )

    return bytes(pdf.output())
