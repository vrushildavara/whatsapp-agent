import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.common.settings import settings


def send_email(to_email: str, code: str) -> None:
    """Send password reset email (used by BackgroundTasks)"""
    try:
        subject = "Password Reset Code"
        body = f"""
    Hello,

    We received a request to reset the password associated with your account.

    Your one-time password reset code is:

    {code}

    This code will expire in 10 minutes. For your security, please do not share this code with anyone. Our support team will never ask you to provide it.

    If you did not request a password reset, you can disregard this message. No changes will be made to your account.

    If you need assistance, please contact our Support Team.

    Sincerely,
    Customer Support Team
    """

        msg = MIMEMultipart()
        msg["From"] = settings.mail_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(settings.mail_host, int(settings.mail_port), timeout=10)
        server.starttls()
        server.login(settings.mail_username, settings.mail_password)
        server.sendmail(settings.mail_from, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        raise Exception(f"Email sending failed: {str(e)}")
