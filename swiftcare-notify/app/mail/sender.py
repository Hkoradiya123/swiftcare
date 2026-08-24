import logging
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    body: str,
    pdf_attachment: bytes | None = None,
    attachment_name: str = "document.pdf",
) -> None:
    s = get_settings()

    if s.mock_smtp:
        logger.info("[MOCK_SMTP] to=%s subject=%r body=%r", to, subject, body)
        return

    import aiosmtplib  # ponytail: lazy — not installed in dev/test venv; mocked in tests
    msg = EmailMessage()
    msg["From"] = s.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if pdf_attachment:
        msg.add_attachment(pdf_attachment, maintype="application", subtype="pdf", filename=attachment_name)

    kwargs: dict = {"start_tls": False}
    if s.smtp_user:
        kwargs.update(username=s.smtp_user, password=s.smtp_pass, start_tls=True)

    await aiosmtplib.send(
        msg,
        hostname=s.smtp_host,
        port=s.smtp_port,
        timeout=10,
        **kwargs,
    )
