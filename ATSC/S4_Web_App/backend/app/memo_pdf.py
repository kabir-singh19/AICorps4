"""Memo PDF export (IF-11): the rendered S3 memo with the run ID and generation date in the footer."""
from datetime import datetime, timezone

from fpdf import FPDF

SUBS = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "≤": "<=",
        "≥": ">=", "×": "x", "…": "...", " ": " "}


def latin(text):
    text = "".join(SUBS.get(c, c) for c in text)
    return text.encode("latin-1", "replace").decode("latin-1")


class MemoPDF(FPDF):
    def __init__(self, run_id, generated):
        super().__init__(format="Letter")
        self.run_id, self.generated = run_id, generated
        self.set_auto_page_break(True, margin=18)
        self.set_margins(18, 16, 18)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(90)
        self.cell(0, 6, latin(f"ATSC run {self.run_id} | memo generated {self.generated} | page {self.page_no()} | "
                              "draft for staff review"), align="C")


def memo_pdf(markdown, run_id, generated=None):
    generated = generated or datetime.now(timezone.utc).date().isoformat()
    pdf = MemoPDF(run_id, generated)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for line in markdown.splitlines():
        s = line.rstrip()
        if not s:
            pdf.ln(2)
            continue
        if s.startswith("|"):
            if set(s.replace("|", "").strip()) <= {"-", " "}:
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            pdf.set_font("Courier", size=8)
            w = width / max(len(cells), 1)
            for c in cells:
                pdf.cell(w, 5, latin(c)[:24], border=1)
            pdf.ln(5)
            continue
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            pdf.set_font("Helvetica", "B", {1: 15, 2: 12, 3: 10.5}.get(level, 10))
            pdf.ln(1)
            pdf.multi_cell(width, 6, latin(s.lstrip("#").strip()))
            continue
        pdf.set_font("Helvetica", size=9.5)
        text = s.replace("**", "")
        if text.startswith("- "):
            text = "  - " + text[2:]
        pdf.multi_cell(width, 4.8, latin(text))
    return bytes(pdf.output())
