import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .config import settings

logger = logging.getLogger(__name__)


def send_account_created_email(to_email: str, full_name: str, hospital_name: str, role_name: str, temp_password: str):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping account creation email")
        return

    subject = "Your PinkShieldAI Portal Account Has Been Created"

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
        <div style="background: #14868C; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">PinkShieldAI Portal</h1>
        </div>
        <div style="padding: 30px; border: 1px solid #eee; border-top: none;">
            <p>Dear {full_name or to_email},</p>
            <p>Your account has been created on the PinkShieldAI Breast Cancer Risk Prediction Portal. Below are your login details:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold; color: #14868C;">Hospital</td>
                    <td style="padding: 10px;">{hospital_name}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold; color: #14868C;">Role</td>
                    <td style="padding: 10px;">{role_name}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold; color: #14868C;">Email</td>
                    <td style="padding: 10px;">{to_email}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold; color: #14868C;">Temporary Password</td>
                    <td style="padding: 10px; font-family: monospace; font-size: 16px; letter-spacing: 1px;">{temp_password}</td>
                </tr>
            </table>
            <p style="color: #e91e8c; font-weight: bold;">Please change your password after your first login.</p>
            <p>You can log in at: <a href="https://bc-portal-dev.tanuh.ai/login" style="color: #14868C;">https://bc-portal-dev.tanuh.ai/login</a></p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="font-size: 12px; color: #999;">This is an automated message from the PinkShieldAI Portal. Please do not reply to this email.</p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to_email, msg.as_string())
        logger.info(f"Account creation email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send account creation email to {to_email}: {e}")
