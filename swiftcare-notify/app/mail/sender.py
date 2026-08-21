from email.message import EmailMessage

from app.core.config import get_settings


async def send_email(to: str, subject: str, body: str) -> None:
    import aiosmtplib  # ponytail: lazy — not installed in dev/test venv; mocked in tests
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    kwargs = {}
    if s.smtp_user:
        kwargs.update(username=s.smtp_user, password=s.smtp_pass)

    await aiosmtplib.send(
        msg,
        hostname=s.smtp_host,
        port=s.smtp_port,
        timeout=10,
        **kwargs,
    )
