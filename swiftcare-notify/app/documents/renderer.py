from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))


def render_visit_summary_pdf(context: dict) -> bytes:
    from weasyprint import HTML  # ponytail: lazy — system libs absent on Windows; mocked in tests
    html = _env.get_template("visit_summary.html").render(**context)
    return HTML(string=html).write_pdf()
