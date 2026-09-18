import os
import smtplib
import pytesseract

if os.name == "nt":
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
from email.message import EmailMessage


GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_reset_email(to_email, reset_link):

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Email credentials are not configured.")
        return False

    print("Connecting to Gmail SMTP...")

    msg = EmailMessage()
    msg["Subject"] = "Reset Your Password - Fake Identity Platform"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    msg.set_content(
        f"""Hello,

We received a request to reset your password.

Click the link below to reset your password:

{reset_link}

This link will expire in 1 hour.

If you did not request a password reset, you can safely ignore this email.

Regards,
Fake Identity Platform
"""
    )

    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=10
        ) as smtp:

            print("Connected to Gmail SMTP.")
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

            print("Gmail authentication successful.")

            smtp.send_message(msg)

        print("Password reset email sent successfully.")
        return True

    except Exception as e:
        print("Email sending failed:", repr(e))
        return False