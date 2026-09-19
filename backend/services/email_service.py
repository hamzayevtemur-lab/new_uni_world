import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "noreply@uniworld.uz"))
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() == "true"


def send_email(to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """Sends an email via SMTP if configured, or logs to console as dev fallback."""
    if not text_content:
        text_content = html_content.replace("<br>", "\n").replace("</p>", "\n").replace("<h1>", "").replace("</h1>", "").replace("<h2>", "").replace("</h2>", "")
        import re
        text_content = re.sub('<[^<]+?>', '', text_content)

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        print("\n" + "=" * 60)
        print(f"📧 [DEV EMAIL FALLBACK] (No SMTP Configured)")
        print(f"TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print("-" * 60)
        print(text_content.strip())
        print("=" * 60 + "\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Uni World Admissions <{SMTP_FROM}>"
        msg["To"] = to_email

        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        if SMTP_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        server.quit()
        print(f"[EmailService] Email successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EmailService ERROR] Failed to send email to {to_email}: {e}")
        # Print fallback to console so credentials/codes are never lost
        print("\n" + "=" * 60)
        print(f"📧 [EMERGENCY FALLBACK LOG]")
        print(f"TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print("-" * 60)
        print(text_content.strip())
        print("=" * 60 + "\n")
        return False


def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Sends a 6-digit email verification OTP code to the student."""
    subject = f"🔑 Your Uni World Verification Code: {otp_code}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #1e3a8a; margin: 0;">🎓 Uni World Overseas Education</h2>
            <p style="color: #64748b; font-size: 14px;">Portal Access Verification</p>
        </div>
        <div style="background: #f8fafc; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <p style="color: #334155; margin-top: 0;">Your 6-digit email verification code is:</p>
            <div style="font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #2563eb; margin: 15px 0;">{otp_code}</div>
            <p style="color: #94a3b8; font-size: 12px; margin-bottom: 0;">This code will expire in 15 minutes.</p>
        </div>
        <p style="color: #64748b; font-size: 13px; line-height: 1.5;">
            Enter this code on the Student Portal request page to verify your email address. If you did not request access, please ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="color: #94a3b8; font-size: 11px; text-align: center;">Uni World Overseas Education Consulting © 2026</p>
    </div>
    """
    return send_email(to_email, subject, html)


def send_student_credentials_email(to_email: str, full_name: str, password: str, login_url: str = "http://127.0.0.1:4000/student") -> bool:
    """Sends login credentials to an approved student."""
    subject = "🎉 Welcome to Uni World! Your Student Portal Credentials"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #1e3a8a; margin: 0;">🎓 Uni World Overseas Education</h2>
            <p style="color: #10b981; font-weight: bold; font-size: 15px; margin-top: 5px;">✅ Portal Access Approved!</p>
        </div>
        <p style="color: #334155; font-size: 15px;">Dear <strong>{full_name}</strong>,</p>
        <p style="color: #475569; font-size: 14px; line-height: 1.6;">
            We are pleased to inform you that your request for access to the Uni World Student Portal has been verified and approved by our admissions team.
        </p>
        <div style="background: #f1f5f9; padding: 18px; border-radius: 8px; border-left: 4px solid #2563eb; margin: 20px 0;">
            <p style="margin: 0 0 8px 0; color: #334155; font-size: 14px;"><strong>Student Portal Credentials:</strong></p>
            <p style="margin: 4px 0; font-family: monospace; font-size: 14px; color: #1e293b;"><strong>Email:</strong> {to_email}</p>
            <p style="margin: 4px 0; font-family: monospace; font-size: 14px; color: #1e293b;"><strong>Temporary Password:</strong> <span style="background: #e2e8f0; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{password}</span></p>
        </div>
        <div style="text-align: center; margin: 25px 0;">
            <a href="{login_url}" style="background: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: bold; display: inline-block;">Log In to Student Portal →</a>
        </div>
        <p style="color: #64748b; font-size: 13px; line-height: 1.5;">
            You can use these credentials to track your university applications, submit required documents, and communicate with your assigned counselor.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="color: #94a3b8; font-size: 11px; text-align: center;">Uni World Overseas Education Consulting © 2026</p>
    </div>
    """
    return send_email(to_email, subject, html)
