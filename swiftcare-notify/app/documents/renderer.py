from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))


def _html_to_pdf(html: str) -> bytes:
    from xhtml2pdf import pisa
    buf = BytesIO()
    pisa.CreatePDF(html, dest=buf)
    return buf.getvalue()


def render_visit_summary_pdf(context: dict) -> bytes:
    return _html_to_pdf(_env.get_template("visit_summary.html").render(**context))


def render_prescription_pdf(context: dict) -> bytes:
    return _html_to_pdf(_env.get_template("prescription.html").render(**context))
