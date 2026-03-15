from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


OUTPUT_PATH = Path("output/pdf/paddington-bot-app-summary.pdf")


TITLE = "Paddington Bot Backend"
TAGLINE = "One-page repo summary"

WHAT_IT_IS = (
    "A FastAPI backend for a WhatsApp community assistant built around the Meta WhatsApp Cloud API. "
    "It supports exchange offers, sale listings, community events, summaries, and simple conversational state."
)

WHO_ITS_FOR = (
    "Primary user: a Leeds community member or organizer using WhatsApp to post or find local exchange offers, "
    "marketplace listings, and events."
)

FEATURES = [
    "Verifies Meta webhook requests and processes inbound WhatsApp text messages.",
    "Sends outbound WhatsApp replies through the Meta Graph API.",
    "Handles help, summary, exchange, listing, and event bot flows.",
    "Stores users, messages, exchange offers, listings, and events in PostgreSQL.",
    "Keeps active multi-step conversation state in Redis and mirrors snapshots to PostgreSQL.",
    "Exposes REST endpoints for health, offers, listings, events, summaries, and webhook intake.",
    "Can use an OpenAI-compatible LLM for intent classification and data extraction, with rule-based fallback.",
]

HOW_IT_WORKS = (
    "FastAPI creates shared Redis and httpx clients, then serves REST routes plus /webhook/meta. "
    "WebhookService normalizes inbound Meta payloads, stores inbound messages, and calls MessageRouter. "
    "MessageRouter uses ConversationStateService plus exchange, listing, event, and summary services; "
    "those services persist through SQLAlchemy repositories into PostgreSQL. Active conversation state also "
    "lives in Redis. WhatsAppService sends reply text back through the Meta Graph API. An optional "
    "OpenAI-compatible provider augments intent classification and structured extraction."
)

HOW_TO_RUN = [
    "Copy .env.example to .env and fill the required values.",
    "Run: docker compose up --build",
    "Run: docker compose exec app alembic upgrade head",
    "Open http://localhost:8000 or call /health",
]

EVIDENCE = (
    "Based on README.md, app/main.py, app/api/deps.py, app/services/webhook_service.py, "
    "app/services/message_router.py, app/services/whatsapp_service.py, "
    "app/services/conversation_state_service.py, app/services/summary_service.py, and the initial Alembic schema."
)


class Layout:
    def __init__(self, pdf: canvas.Canvas) -> None:
        self.pdf = pdf
        self.width, self.height = letter
        self.margin = 0.55 * inch
        self.gutter = 0.35 * inch
        self.left_col_width = 3.35 * inch
        self.right_col_width = self.width - (2 * self.margin) - self.gutter - self.left_col_width
        self.bottom_limit = 0.45 * inch

    def draw_header(self) -> float:
        pdf = self.pdf
        top = self.height - self.margin
        band_height = 0.78 * inch
        pdf.setFillColor(colors.HexColor("#153B50"))
        pdf.roundRect(self.margin, top - band_height, self.width - (2 * self.margin), band_height, 12, fill=1, stroke=0)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(self.margin + 16, top - 28, TITLE)
        pdf.setFont("Helvetica", 10.5)
        pdf.drawString(self.margin + 16, top - 45, TAGLINE)
        return top - band_height - 14

    def draw_section_heading(self, x: float, y: float, title: str, width: float) -> float:
        pdf = self.pdf
        pdf.setFillColor(colors.HexColor("#0F5B78"))
        pdf.roundRect(x, y - 12, width, 15, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x + 8, y - 8, title.upper())
        return y - 20

    def draw_paragraph(self, x: float, y: float, width: float, text: str, font_size: float = 9.2, leading: float = 11.2) -> float:
        pdf = self.pdf
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", font_size)
        lines = wrap_text(text, width, font_size, "Helvetica")
        for line in lines:
            pdf.drawString(x, y, line)
            y -= leading
        return y

    def draw_bullets(
        self,
        x: float,
        y: float,
        width: float,
        items: list[str],
        font_size: float = 8.95,
        leading: float = 10.8,
        bullet_indent: float = 8,
        text_indent: float = 16,
    ) -> float:
        pdf = self.pdf
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", font_size)
        text_width = width - text_indent
        for item in items:
            lines = wrap_text(item, text_width, font_size, "Helvetica")
            pdf.drawString(x + bullet_indent, y, "-")
            pdf.drawString(x + text_indent, y, lines[0])
            y -= leading
            for line in lines[1:]:
                pdf.drawString(x + text_indent, y, line)
                y -= leading
            y -= 1.5
        return y

    def ensure_page_fit(self, y: float) -> None:
        if y < self.bottom_limit:
            raise RuntimeError(f"Layout overflowed the page at y={y:.2f}")


def wrap_text(text: str, width: float, font_size: float, font_name: str) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if stringWidth(trial, font_name, font_size) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def build_pdf() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT_PATH), pagesize=letter)
    pdf.setTitle("Paddington Bot App Summary")
    pdf.setAuthor("OpenAI Codex")
    pdf.setSubject("Repo-derived one-page application summary")

    layout = Layout(pdf)
    y_start = layout.draw_header()

    left_x = layout.margin
    right_x = layout.margin + layout.left_col_width + layout.gutter
    left_y = y_start
    right_y = y_start

    left_y = layout.draw_section_heading(left_x, left_y, "What it is", layout.left_col_width)
    left_y = layout.draw_paragraph(left_x, left_y, layout.left_col_width, WHAT_IT_IS)
    left_y -= 8

    left_y = layout.draw_section_heading(left_x, left_y, "Who it's for", layout.left_col_width)
    left_y = layout.draw_paragraph(left_x, left_y, layout.left_col_width, WHO_ITS_FOR)
    left_y -= 8

    left_y = layout.draw_section_heading(left_x, left_y, "What it does", layout.left_col_width)
    left_y = layout.draw_bullets(left_x, left_y, layout.left_col_width, FEATURES)

    right_y = layout.draw_section_heading(right_x, right_y, "How it works", layout.right_col_width)
    right_y = layout.draw_paragraph(right_x, right_y, layout.right_col_width, HOW_IT_WORKS, font_size=9.0, leading=10.8)
    right_y -= 8

    right_y = layout.draw_section_heading(right_x, right_y, "How to run", layout.right_col_width)
    right_y = layout.draw_bullets(right_x, right_y, layout.right_col_width, HOW_TO_RUN, font_size=9.0, leading=10.8)
    right_y -= 4

    evidence_heading_y = min(left_y, right_y)
    evidence_width = layout.width - (2 * layout.margin)
    evidence_heading_y = layout.draw_section_heading(layout.margin, evidence_heading_y, "Repo evidence", evidence_width)
    evidence_heading_y = layout.draw_paragraph(
        layout.margin,
        evidence_heading_y,
        evidence_width,
        EVIDENCE,
        font_size=8.0,
        leading=9.5,
    )

    layout.ensure_page_fit(min(left_y, right_y, evidence_heading_y))
    pdf.showPage()
    pdf.save()

    reader = PdfReader(str(OUTPUT_PATH))
    if len(reader.pages) != 1:
        raise RuntimeError(f"Expected exactly 1 page, found {len(reader.pages)}")


if __name__ == "__main__":
    build_pdf()
