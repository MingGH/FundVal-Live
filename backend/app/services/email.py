import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from ..config import Config

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, content: str, is_html: bool = False, user_id: int = None):
    """
    Send an email using SMTP settings.
    If user_id is provided, use per-user SMTP config; otherwise fall back to global Config.
    """
    smtp_host = None
    smtp_port = None
    smtp_user = None
    smtp_password = None
    email_from = None

    if user_id is not None:
        try:
            from ..routers.settings import get_user_effective_settings
            settings = get_user_effective_settings(user_id)
            smtp_host = settings.get("SMTP_HOST")
            smtp_port = settings.get("SMTP_PORT")
            smtp_user = settings.get("SMTP_USER")
            smtp_password = settings.get("SMTP_PASSWORD")
            email_from = settings.get("EMAIL_FROM")
        except Exception as e:
            logger.warning(f"Failed to load user {user_id} SMTP settings, falling back to global: {e}")

    # Fall back to global config if user settings not available
    if not smtp_host:
        smtp_host = Config.SMTP_HOST
    if not smtp_port:
        smtp_port = Config.SMTP_PORT
    if not smtp_user:
        smtp_user = Config.SMTP_USER
    if not smtp_password:
        smtp_password = Config.SMTP_PASSWORD
    if not email_from:
        email_from = Config.EMAIL_FROM

    if not smtp_host or not smtp_user:
        logger.warning("SMTP not configured. Skipping email send.")
        return False

    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = to_email
    msg['Subject'] = subject

    if is_html:
        msg.attach(MIMEText(content, 'html'))
    else:
        msg.attach(MIMEText(content, 'plain'))

    try:
        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
