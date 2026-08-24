import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.mail.sender import send_email


def _settings(**kwargs) -> Settings:
    return Settings(database_url="sqlite:///:memory:", **kwargs)


@pytest.mark.asyncio
async def test_mock_smtp_skips_network_call(caplog):
    """mock_smtp=True must log the email and never touch the network."""
    import logging
    with (
        patch("app.mail.sender.get_settings", return_value=_settings(mock_smtp=True)),
        caplog.at_level(logging.INFO, logger="app.mail.sender"),
    ):
        await send_email("patient@example.com", "Hello", "Body")

    assert any("[MOCK_SMTP]" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_no_credentials_sends_without_starttls():
    """Plain SMTP (no credentials) → start_tls=False, no username/password."""
    mock_lib = MagicMock()
    mock_lib.send = AsyncMock()

    with (
        patch("app.mail.sender.get_settings", return_value=_settings(smtp_host="mailhog", smtp_port=1025)),
        patch.dict(sys.modules, {"aiosmtplib": mock_lib}),
    ):
        await send_email("patient@example.com", "Subject", "Body")

    _, kw = mock_lib.send.call_args
    assert kw["start_tls"] is False
    assert "username" not in kw
    assert "password" not in kw


@pytest.mark.asyncio
async def test_credentials_enable_starttls():
    """SMTP credentials present → start_tls=True, username + password forwarded."""
    mock_lib = MagicMock()
    mock_lib.send = AsyncMock()

    with (
        patch("app.mail.sender.get_settings", return_value=_settings(
            smtp_host="smtp.example.com", smtp_port=587, smtp_user="u", smtp_pass="p",
        )),
        patch.dict(sys.modules, {"aiosmtplib": mock_lib}),
    ):
        await send_email("patient@example.com", "Subject", "Body")

    _, kw = mock_lib.send.call_args
    assert kw["start_tls"] is True
    assert kw["username"] == "u"
    assert kw["password"] == "p"
