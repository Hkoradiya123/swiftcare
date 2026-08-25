import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

recipient_user = "koradiyaharsh94@gmail.com"

def load_env(env_path: Path) -> dict:
    config = {}
    if not env_path.exists():
        print(f"Warning: {env_path} not found!")
        return config
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip("'\"")
    return config

def main():
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env"
    env = load_env(env_path)

    smtp_host = env.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(env.get("SMTP_PORT", "587"))
    smtp_user = env.get("SMTP_USER", "")
    smtp_pass = env.get("SMTP_PASS", "")
    mail_from = env.get("MAIL_FROM", smtp_user)
    recipient = recipient_user

    print("=" * 50)
    print("SwiftCare SMTP Test Configuration:")
    print(f"  Host     : {smtp_host}")
    print(f"  Port     : {smtp_port}")
    print(f"  User     : {smtp_user}")
    print(f"  Pass     : {'***' if smtp_pass else '(empty)'}")
    print(f"  From     : {mail_from}")
    print(f"  To       : {recipient}")
    print("=" * 50)

    if not smtp_user or not smtp_pass:
        print("ERROR: SMTP_USER or SMTP_PASS is missing in .env!")
        return

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = recipient
    msg["Subject"] = "SwiftCare SMTP Test Email"
    msg.set_content(
        "Hello!\n\n"
        "This is a test email sent from SwiftCare to verify your SMTP and +noreply setup.\n\n"
        f"Sender (From) : {mail_from}\n"
        f"Recipient (To): {recipient}\n"
        "SMTP Status   : Connected & Authenticated Successfully!\n\n"
        "Regards,\nSwiftCare System"
    )

    try:
        print(f"Connecting to {smtp_host}:{smtp_port}...")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)

        print("Starting TLS (STARTTLS)...")
        server.starttls()

        print(f"Authenticating as {smtp_user}...")
        server.login(smtp_user, smtp_pass)

        print(f"Sending test email from '{mail_from}' to '{recipient}'...")
        server.send_message(msg)
        server.quit()

        print("\n" + "=" * 50)
        print("SUCCESS! Test email sent successfully.")
        print(f"Please check your inbox at: {recipient}")
        print("=" * 50)
    except Exception as e:
        print("\n" + "=" * 50)
        print(f"FAILED to send email! Error:\n{e}")
        print("=" * 50)

if __name__ == "__main__":
    main()
