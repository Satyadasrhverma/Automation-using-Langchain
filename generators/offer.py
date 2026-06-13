import base64
from datetime import datetime
from fpdf import FPDF, XPos, YPos


def generate_offer_letter(record: dict, job_details: dict, groq_client) -> tuple[str, str]:
    name       = record.get("name", "Candidate")
    skills     = record.get("skills", "—")
    company    = job_details.get("company", "Our Company")
    position   = job_details.get("position", "the offered position")
    department = job_details.get("department", "")
    start_date = job_details.get("start_date", "To be confirmed")
    salary     = job_details.get("salary", "")

    skills_text = skills if skills != "—" else "your relevant qualifications"
    first_name  = name.split()[0] if name else "Candidate"
    dept_line   = f" in the {department} Department" if department else ""
    salary_line = f"\n- Compensation: {salary}" if salary else ""

    prompt = (
        f"Write a formal job offer letter email from the HR team to {name} "
        f"offering them the position of {position}{dept_line} at {company}.\n\n"
        f"Candidate skills: {skills_text}\n"
        f"Start date: {start_date}{salary_line}\n\n"
        "Requirements:\n"
        "- Subject line at the very top\n"
        "- Address by first name only\n"
        "- Professional, warm HR tone\n"
        "- Mention their skills as the reason for selection\n"
        "- Include: congratulations, position title, start date, next steps\n"
        "- Reference 'the attached PDF offer letter' for complete terms\n"
        "- End with HR team sign-off\n"
        "- 3–4 paragraphs\n\n"
        "Format exactly as:\nSubject: <subject line>\n\n<email body>"
    )

    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    email_text = completion.choices[0].message.content.strip()
    pdf_bytes  = _build_pdf(
        name, first_name, record.get("email", ""),
        company, position, department, start_date, salary, skills_text,
    )
    return email_text, base64.b64encode(pdf_bytes).decode()


def _build_pdf(name, first_name, email, company, position, department, start_date, salary, skills_text) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(25, 20, 25)
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Company header ──
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 12, company, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, "Human Resources Department", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(3)
    pdf.set_draw_color(79, 70, 229)
    pdf.set_line_width(0.8)
    pdf.line(25, pdf.get_y(), 185, pdf.get_y())
    pdf.ln(8)

    # ── Date & recipient ──
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, datetime.today().strftime("%B %d, %Y"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if email:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, email, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # ── Title ──
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 9, "OFFER OF EMPLOYMENT", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_draw_color(79, 70, 229)
    pdf.set_line_width(0.4)
    pdf.line(25, pdf.get_y(), 185, pdf.get_y())
    pdf.ln(7)

    # ── Greeting ──
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, f"Dear {first_name},", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # ── Opening paragraph ──
    dept_text = f" within the {department} Department" if department else ""
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        f"We are delighted to offer you the position of {position}{dept_text} at {company}. "
        f"After a thorough review of your qualifications, we are confident that you will be "
        f"a valuable addition to our team."
    )
    pdf.ln(5)

    # ── Offer details box ──
    details = [("Position", position)]
    if department:
        details.append(("Department", department))
    details.append(("Start Date", start_date))
    if salary:
        details.append(("Compensation", salary))

    row_h = 8
    box_h = len(details) * row_h + 12
    box_y = pdf.get_y()
    pdf.set_fill_color(238, 240, 255)
    pdf.set_draw_color(79, 70, 229)
    pdf.set_line_width(0.3)
    pdf.rect(25, box_y, 160, box_h, style="FD")
    pdf.set_xy(25, box_y + 5)
    for label, value in details:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(30)
        pdf.cell(50, row_h, label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, row_h, str(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    # ── Skills paragraph ──
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        f"Your expertise in {skills_text} was a key factor in our decision and aligns strongly "
        f"with the requirements of this role. We look forward to the contribution you will make."
    )
    pdf.ln(4)

    # ── Next steps ──
    pdf.multi_cell(0, 6,
        "Please review this offer carefully. To accept, sign and return this letter by the acceptance "
        "deadline below. Should you have any questions, do not hesitate to contact our HR department."
    )
    pdf.ln(5)
    pdf.cell(0, 6, "Acceptance deadline: ___________________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # ── Sign-off ──
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Sincerely,", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(12)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Human Resources Team", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, company, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.3)
    pdf.line(25, pdf.get_y(), 100, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, "Authorized Signature & Date", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    # ── Footer ──
    pdf.set_draw_color(79, 70, 229)
    pdf.set_line_width(0.5)
    pdf.line(25, pdf.get_y(), 185, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5,
        f"Confidential - Generated on {datetime.today().strftime('%B %d, %Y')}.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )

    return bytes(pdf.output())
