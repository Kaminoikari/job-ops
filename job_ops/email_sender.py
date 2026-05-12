"""Gmail SMTP sender — Python equivalent of nodemailer."""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


@dataclass
class SendResult:
    ok: bool
    reason: str = ""


def send_daily_email(
    *,
    subject: str,
    text: str,
    html: str,
    sender: str | None,
    app_password: str | None,
    recipient: str | None,
) -> SendResult:
    if not sender or not app_password or not recipient:
        missing = [
            name for name, val in [
                ("GMAIL_USER", sender),
                ("GMAIL_APP_PASSWORD", app_password),
                ("NOTIFY_EMAIL_TO", recipient),
            ] if not val
        ]
        return SendResult(False, f"缺少環境變數：{', '.join(missing)}")

    msg = MIMEMultipart("alternative")
    msg["From"] = f"job-ops <{sender}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as s:
            s.login(sender, app_password)
            s.sendmail(sender, [recipient], msg.as_string())
        return SendResult(True)
    except smtplib.SMTPAuthenticationError as e:
        return SendResult(False, f"SMTP 認證失敗：{e}")
    except Exception as e:
        return SendResult(False, str(e))
