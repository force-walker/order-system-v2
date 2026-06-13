from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


# Current invoice schema does not persist issuer/bank/payment master data yet,
# so PDF output uses centralized defaults here for easy future replacement.
ISSUER_NAME = "Kaijin Trading (Hong Kong) Co., Limited"
ISSUER_ADDRESS_LINES = ["Hong Kong"]
PAYABLE_TO = "HSBC Limited (004)"
ACCOUNT_NAME = "Kaijin Trading (Hong Kong) Co., Limited"
BANK_ACCOUNT_NO = "049-869308-838"
DEFAULT_CURRENCY = "HK$"


@dataclass
class InvoicePdfLine:
    description: str
    source: str
    quantity: float
    unit_price: float
    amount: float


@dataclass
class InvoicePdfDocument:
    invoice_no: str
    invoice_date: date
    due_date: date | None
    customer_name: str
    customer_address_lines: list[str] = field(default_factory=list)
    untaxed_amount: float = 0
    total: float = 0
    tax_total: float = 0
    payment_terms: str = ""
    payment_communication: str = ""
    currency: str = DEFAULT_CURRENCY
    lines: list[InvoicePdfLine] = field(default_factory=list)


def _pick_font() -> str:
    candidates = [
        ("NotoSansCJKjp", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
        ("IPAexGothic", Path("/usr/share/fonts/truetype/ipaexg/ipaexg.ttf")),
    ]
    for name, path in candidates:
        if not path.exists():
            continue
        try:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
            return name
        except Exception:
            continue
    fallback = "HeiseiKakuGo-W5"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback


def _format_currency(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _format_quantity(quantity: float) -> str:
    return f"{quantity:,.3f}".rstrip("0").rstrip(".")


def _format_unit_price(unit_price: float) -> str:
    return f"{unit_price:,.2f}"


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_w: float, max_lines: int) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if c.stringWidth(candidate, font, size) <= max_w:
            current = candidate
            continue
        lines.append(current)
        current = ch
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and current and lines[-1] != current:
        ellipsis = "..."
        trimmed = lines[-1]
        while trimmed and c.stringWidth(trimmed + ellipsis, font, size) > max_w:
            trimmed = trimmed[:-1]
        lines[-1] = (trimmed + ellipsis) if trimmed else ellipsis
    return lines or [""]


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states) + 1
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total_pages)
            canvas.Canvas.showPage(self)
        self._draw_page_number(total_pages)
        canvas.Canvas.save(self)

    def _draw_page_number(self, total_pages: int):
        font = _pick_font()
        self.setFont(font, 9)
        self.drawRightString(A4[0] - 36, 24, f"Page {self._pageNumber} / {total_pages}")


def build_invoice_pdf(doc: InvoicePdfDocument) -> bytes:
    font = _pick_font()
    buf = BytesIO()
    c = NumberedCanvas(buf, pagesize=A4, pageCompression=1)
    width, height = A4
    left = 40
    right = width - 40
    bottom_limit = 90

    def draw_header() -> float:
        y = height - 44
        c.setFont(font, 12)
        c.drawString(left, y, ISSUER_NAME)
        y -= 14
        c.setFont(font, 9)
        for line in ISSUER_ADDRESS_LINES:
            c.drawString(left, y, line)
            y -= 12
        c.drawString(left, y, f"Payable to: {PAYABLE_TO}")
        y -= 12
        c.drawString(left, y, f"Account Name: {ACCOUNT_NAME}")
        y -= 12
        c.drawString(left, y, f"Bank Account No.: {BANK_ACCOUNT_NO}")

        meta_top = height - 52
        c.setFont(font, 18)
        c.drawRightString(right, meta_top, f"Invoice {doc.invoice_no}")
        c.setFont(font, 9)
        meta_y = meta_top - 28
        c.drawRightString(right - 120, meta_y, "Invoice Date")
        c.drawRightString(right, meta_y, doc.invoice_date.strftime("%m/%d/%Y"))
        meta_y -= 16
        c.drawRightString(right - 120, meta_y, "Due Date")
        c.drawRightString(right, meta_y, doc.due_date.strftime("%m/%d/%Y") if doc.due_date else "-")

        bill_y = height - 170
        c.setFont(font, 11)
        c.drawString(left, bill_y, doc.customer_name)
        c.setFont(font, 9)
        for idx, line in enumerate(doc.customer_address_lines):
            c.drawString(left, bill_y - ((idx + 1) * 12), line)

        table_y = height - 242
        c.setLineWidth(0.7)
        c.line(left, table_y, right, table_y)
        c.setFont(font, 9)
        columns = [("Description", 240), ("Source", 70), ("Quantity", 70), ("Unit Price", 80), ("Amount", 95)]
        x = left
        for label, col_w in columns:
            c.drawString(x + 4, table_y - 14, label)
            x += col_w
        c.line(left, table_y - 20, right, table_y - 20)
        return table_y - 34

    def ensure_space(y: float, needed: float) -> float:
        if y - needed >= bottom_limit:
            return y
        c.showPage()
        return draw_header()

    y = draw_header()
    desc_w = 232
    source_w = 62
    quantity_x = left + 240 + 70 + 70
    unit_price_x = left + 240 + 70 + 70 + 80
    amount_x = right

    for line in doc.lines:
        desc_lines = _wrap_text(c, line.description, font, 9, desc_w, 3)
        source_lines = _wrap_text(c, line.source, font, 9, source_w, 2)
        line_count = max(len(desc_lines), len(source_lines), 1)
        needed = (line_count * 11) + 8
        y = ensure_space(y, needed)

        top = y
        c.setFont(font, 9)
        for idx, row in enumerate(desc_lines):
            c.drawString(left + 4, top - (idx * 11), row)
        for idx, row in enumerate(source_lines):
            c.drawString(left + 244, top - (idx * 11), row)

        c.drawRightString(quantity_x + 66, top, _format_quantity(line.quantity))
        c.drawRightString(unit_price_x + 76, top, _format_unit_price(line.unit_price))
        c.drawRightString(amount_x, top, _format_currency(line.amount, doc.currency))
        y -= needed
        c.line(left, y + 2, right, y + 2)

    summary_needed = 120
    y = ensure_space(y, summary_needed)
    summary_top = y - 10
    c.setFont(font, 10)
    c.drawString(left, summary_top, f"Payment terms: {doc.payment_terms}")
    c.drawString(left, summary_top - 18, f"Payment Communication: {doc.payment_communication}")

    box_left = right - 180
    c.setFont(font, 10)
    c.drawString(box_left, summary_top, "Untaxed Amount")
    c.drawRightString(right, summary_top, _format_currency(doc.untaxed_amount, doc.currency))
    if doc.tax_total:
        c.drawString(box_left, summary_top - 18, "Taxes")
        c.drawRightString(right, summary_top - 18, _format_currency(doc.tax_total, doc.currency))
        total_y = summary_top - 40
    else:
        total_y = summary_top - 22
    c.setFont(font, 11)
    c.drawString(box_left, total_y, "Total")
    c.drawRightString(right, total_y, _format_currency(doc.total, doc.currency))

    c.save()
    return buf.getvalue()
