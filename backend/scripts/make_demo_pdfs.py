"""
Generate demo PDFs using ReportLab with realistic filler text, explicit page breaks,
and specific ground-truth facts for VaultRAG Step 2 ingestion and Step 3 leak testing.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors

PDF_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"


def build_pdf(filename: str, story: list) -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_DIR / filename
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    doc.build(story)
    print(f"  + Generated {filename}")


def make_hr_policy(styles):
    story = [
        Paragraph("VaultRAG Enterprise - General HR Policy", styles["Title"]),
        Spacer(1, 14),
        Paragraph("1. Code of Conduct & Workplace Standards", styles["Heading2"]),
        Paragraph(
            "VaultRAG is committed to maintaining a safe, inclusive, and professional workplace environment. "
            "All employees are expected to uphold the highest standards of integrity, respect, and compliance "
            "with organizational values and statutory guidelines across all operations and communications.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Standard business working hours are scheduled from 9:00 AM to 6:00 PM, Monday through Friday. "
            "Flexible working arrangements may be coordinated with department leads based on project deliverables "
            "and organizational requirements.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 2
        Paragraph("2. Leave Entitlements & Absence Guidelines", styles["Heading2"]),
        Paragraph(
            "Every employee receives 20 days of paid leave per year. "
            "This statutory paid time off is designed to ensure work-life balance and rest. Leave requests "
            "should be submitted through the employee self-service portal at least five working days in advance "
            "for planned absences.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "In addition to annual leave, employees are entitled to standard national holidays, bereavement leave, "
            "and medical leave upon submission of valid medical certification for absences exceeding three consecutive days.",
            styles["Normal"],
        ),
    ]
    build_pdf("hr_policy.pdf", story)


def make_leave_policy_summary(styles):
    story = [
        Paragraph("Leave Policy Summary (Public Overview)", styles["Title"]),
        Spacer(1, 14),
        Paragraph("1. Summary of Annual Leave Provisions", styles["Heading2"]),
        Paragraph(
            "This document provides a general summary of employee leave policies applicable across the organization. "
            "Every employee receives 20 days of paid leave per year. "
            "Leave is accrued on a monthly basis and is available for utilization upon completion of probation.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Employees are encouraged to plan their vacations proactively to ensure operational continuity within teams.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 2
        Paragraph("2. Workflow and Approval Matrix", styles["Heading2"]),
        Paragraph(
            "All leave requests must be logged through the internal HR portal. Direct line managers review and approve "
            "requests based on project coverage. Standard turnaround time for approval is two business days.",
            styles["Normal"],
        ),
    ]
    build_pdf("leave_policy_summary.pdf", story)


def make_leave_policy_full(styles):
    story = [
        Paragraph("Comprehensive Leave Policy & Executive Benefits", styles["Title"]),
        Spacer(1, 14),
        Paragraph("1. Policy Scope and Classification Framework", styles["Heading2"]),
        Paragraph(
            "This internal HR document defines the detailed regulations governing annual leave, executive benefits, "
            "accrual mechanisms, and specialized leave categories for staff members and management personnel.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Classification: Internal / Confidential. Authorized distribution is restricted to Human Resources "
            "and executive administration personnel.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 2
        Paragraph("2. Executive Compensation and Leave Encashment", styles["Heading2"]),
        Paragraph(
            "Executive management members are eligible for specialized compensation packages upon contract completion. "
            "Executive leave encashment is capped at 45 days. "
            "Encashment calculations are derived from basic monthly compensation without additional discretionary bonuses.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Encashment disbursements must be reviewed and countersigned by the HR Director and Finance Controller "
            "prior to end-of-year payroll reconciliation.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 3
        Paragraph("3. Annual Carry-Forward and Sabbatical Guidelines", styles["Heading2"]),
        Paragraph(
            "To prevent excessive liability accumulation, annual carry-forward thresholds are strictly enforced. "
            "Unused leave carry-forward is limited to 8 days. "
            "Any surplus unused leave beyond this threshold at the end of the calendar year will lapse automatically.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Extended sabbaticals for research or continuous education require minimum five years of continuous service "
            "and formal executive committee authorization.",
            styles["Normal"],
        ),
    ]
    build_pdf("leave_policy_full.pdf", story)


def make_board_minutes(styles):
    story = [
        # Page 1
        Paragraph("Board of Directors - Quarterly Meeting Minutes", styles["Title"]),
        Spacer(1, 14),
        Paragraph("Meeting Reference: BOD-2026-Q3 | Classification: Strictly Confidential", styles["Normal"]),
        Spacer(1, 10),
        Paragraph(
            "The quarterly meeting of the Board of Directors was convened on October 1, 2026. "
            "Attendees included the Chief Executive Officer, Chief Technology Officer, and independent directors. "
            "The primary focus was establishing strategic investments and organizational governance directives.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 2
        Paragraph("Strategic Initiatives & Enterprise Architecture", styles["Heading2"]),
        Paragraph(
            "The committee evaluated progress on modernizing data infrastructure and implementing the VaultRAG "
            "secure multi-modal retrieval system. Emphasis was placed on ensuring robust access control boundaries "
            "across multi-tenant vector repositories.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 3
        Paragraph("Operational Performance & Expansion Roadmap", styles["Heading2"]),
        Paragraph(
            "Operational performance across technology divisions demonstrated high compliance and throughput. "
            "Resource allocation targets were aligned with future scaling requirements.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 4
        Paragraph("Financial Appropriations & Budget Authorization", styles["Heading2"]),
        Paragraph(
            "Following review of growth projections and market opportunities, the committee finalized departmental allocations. "
            "The board approved a marketing budget of Rs. 12 lakh for Q3. "
            "The allocation covers digital acquisition channels, customer outreach summits, and developer ecosystem expansion.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Quarterly variance reports will be prepared by the marketing operations team and submitted for monthly review.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 5
        Paragraph("Resolutions and Executive Sign-Off", styles["Heading2"]),
        Paragraph(
            "All financial resolutions were duly proposed, seconded, and passed unanimously by the board. "
            "Approval was recorded by the finance head. "
            "The meeting concluded with directives to schedule the subsequent review in January 2027.",
            styles["Normal"],
        ),
    ]
    build_pdf("board_minutes.pdf", story)


def make_vendor_contract(styles):
    table_data = [
        ["Description", "Amount (INR)"],
        ["Software licence", "Rs. 2,40,000"],
        ["Implementation", "Rs. 2,00,000"],
        ["Training", "Rs. 80,000"],
        ["Support (1 year)", "Rs. 1,00,000"],
        ["Total", "Rs. 6,20,000"],
    ]
    t = Table(table_data, colWidths=[240, 160])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    story = [
        # Page 1
        Paragraph("Master Services Agreement & Statement of Work", styles["Title"]),
        Spacer(1, 14),
        Paragraph("1. Parties and Engagement Scope", styles["Heading2"]),
        Paragraph(
            "This Agreement is entered into between VaultRAG Solutions and Enterprise Software Providers Ltd. "
            "The vendor agrees to supply software licenses, deployment services, and continuous maintenance.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 2
        Paragraph("2. Financial Considerations & Fee Structure", styles["Heading2"]),
        Paragraph(
            "The contract value is Rs. 6,20,000. "
            "Payments shall be disbursed in installments aligned with milestone acceptance and verified SLA metrics.",
            styles["Normal"],
        ),
        Spacer(1, 12),
        t,
        Spacer(1, 12),
        PageBreak(),  # PAGE 3
        Paragraph("3. Terms, Warranties, and Signatures", styles["Heading2"]),
        Paragraph(
            "The engagement shall remain valid for a term of twelve months from execution. "
            "Both parties warrant full compliance with statutory confidentiality and intellectual property obligations.",
            styles["Normal"],
        ),
    ]
    build_pdf("vendor_contract.pdf", story)


def make_finance_memo(styles):
    story = [
        # Page 1
        Paragraph("Internal Finance Memorandum - Q3 Disbursements", styles["Title"]),
        Spacer(1, 14),
        Paragraph("Disbursement Verification & Accounts Payable", styles["Heading2"]),
        Paragraph(
            "The accounts department has completed validation for immediate vendor reconciliation. "
            "Invoice 1042 total is Rs. 48,500. "
            "The invoice corresponds to specialized security hardware and token dispatch services received in August.",
            styles["Normal"],
        ),
        Spacer(1, 10),
        Paragraph(
            "Verification confirms that all purchase orders and receipt notes have been matched and signed by authorized personnel.",
            styles["Normal"],
        ),
        PageBreak(),  # PAGE 2
        Paragraph("Tax Deductions and Audit Documentation", styles["Heading2"]),
        Paragraph(
            "Applicable tax deductions at source have been calculated and deducted according to tax regulations. "
            "All payment vouchers have been submitted to internal audit archives for year-end compliance review.",
            styles["Normal"],
        ),
    ]
    build_pdf("finance_memo.pdf", story)


def main():
    styles = getSampleStyleSheet()
    print("Generating demo PDFs in data/pdfs/ ...")
    make_hr_policy(styles)
    make_leave_policy_summary(styles)
    make_leave_policy_full(styles)
    make_board_minutes(styles)
    make_vendor_contract(styles)
    make_finance_memo(styles)
    print("All demo PDFs successfully generated.")


if __name__ == "__main__":
    main()
