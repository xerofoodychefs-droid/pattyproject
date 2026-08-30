import html
import logging
from typing import Optional
import httpx
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("patty_project.email_service")

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_TIMEOUT_SECONDS = 10.0


def build_contact_email_html(first_name: str, last_name: str, email: str, subject: str, message: str) -> str:
    """Builds a secure, sanitized, branded HTML email for contact form submissions."""
    safe_first = html.escape(first_name)
    safe_last = html.escape(last_name)
    safe_email = html.escape(email)
    safe_subject = html.escape(subject)
    safe_message = html.escape(message).replace("\n", "<br/>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Patty Project Contact Form Submission</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0c0c0c; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #ffffff;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0c0c0c; padding: 30px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" max-width="600" style="max-width: 600px; background-color: #141414; border: 1px solid #262626; border-radius: 12px; overflow: hidden;">
          <!-- Header -->
          <tr>
            <td style="background-color: #1a1a1a; padding: 24px 30px; border-bottom: 2px solid #FF5500;">
              <table role="presentation" width="100%">
                <tr>
                  <td>
                    <span style="font-size: 11px; font-weight: 800; color: #FF5500; letter-spacing: 2px; text-transform: uppercase;">PATTY PROJECT UK</span>
                    <h1 style="margin: 6px 0 0 0; font-size: 22px; font-weight: 900; color: #ffffff; text-transform: uppercase;">New Contact Form Message</h1>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Content Body -->
          <tr>
            <td style="padding: 30px;">
              <!-- Customer Info Grid -->
              <table role="presentation" width="100%" style="margin-bottom: 24px; border-collapse: separate; border-spacing: 0;">
                <tr>
                  <td style="padding: 12px 16px; background-color: #1c1c1c; border-radius: 8px 8px 0 0; border-bottom: 1px solid #2a2a2a;">
                    <span style="font-size: 11px; font-weight: 700; color: #888888; text-transform: uppercase; letter-spacing: 1px;">Sender Name</span>
                    <div style="font-size: 15px; font-weight: 700; color: #ffffff; margin-top: 4px;">{safe_first} {safe_last}</div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; background-color: #1c1c1c; border-bottom: 1px solid #2a2a2a;">
                    <span style="font-size: 11px; font-weight: 700; color: #888888; text-transform: uppercase; letter-spacing: 1px;">Customer Email</span>
                    <div style="font-size: 15px; font-weight: 700; color: #FF5500; margin-top: 4px;">
                      <a href="mailto:{safe_email}" style="color: #FF5500; text-decoration: none;">{safe_email}</a>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; background-color: #1c1c1c; border-radius: 0 0 8px 8px;">
                    <span style="font-size: 11px; font-weight: 700; color: #888888; text-transform: uppercase; letter-spacing: 1px;">Subject</span>
                    <div style="font-size: 15px; font-weight: 600; color: #e5e5e5; margin-top: 4px;">{safe_subject}</div>
                  </td>
                </tr>
              </table>

              <!-- Message Section -->
              <div style="margin-top: 20px;">
                <span style="font-size: 11px; font-weight: 700; color: #888888; text-transform: uppercase; letter-spacing: 1px; display: block; margin-bottom: 8px;">Customer Message</span>
                <div style="background-color: #0e0e0e; border: 1px solid #262626; border-radius: 8px; padding: 18px; font-size: 14px; line-height: 1.6; color: #d1d5db;">
                  {safe_message}
                </div>
              </div>

              <!-- Reply Prompt -->
              <div style="margin-top: 24px; padding: 12px 16px; background-color: #1a1a1a; border-left: 3px solid #FF5500; border-radius: 4px; font-size: 12px; color: #9ca3af;">
                💡 <strong>Tip:</strong> Clicking "Reply" in your email client will reply directly to <strong>{safe_email}</strong>.
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 30px; background-color: #0e0e0e; border-top: 1px solid #222222; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #666666;">
                This message was submitted via the official Patty Project Contact Form on <a href="https://pattyproject.co.uk" style="color: #888888; text-decoration: none;">pattyproject.co.uk</a>.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_contact_email_text(first_name: str, last_name: str, email: str, subject: str, message: str) -> str:
    """Builds a plain-text version of the contact form email."""
    return f"""Patty Project UK — Contact Form Submission
==================================================

Name:           {first_name} {last_name}
Customer Email: {email}
Subject:        {subject}

Message:
--------------------------------------------------
{message}
--------------------------------------------------

Reply directly to this email to respond to the customer ({email}).
"""


def send_contact_email(
    first_name: str,
    last_name: str,
    email: str,
    subject: str,
    message: str,
    client: Optional[httpx.Client] = None,
) -> bool:
    """
    Sends a contact form submission email through Resend API to xerofoodychefs@gmail.com.

    Security:
    - Never exposes or logs RESEND_API_KEY.
    - HTML-escapes all dynamic content.
    - Uses customer email in Reply-To header.
    - Times out safely if Resend is unreachable.
    """
    to_address = settings.CONTACT_EMAIL_TO or "xerofoodychefs@gmail.com"
    from_address = settings.CONTACT_EMAIL_FROM or "Patty Project <website@pattyproject.co.uk>"
    api_key = settings.RESEND_API_KEY

    html_content = build_contact_email_html(first_name, last_name, email, subject, message)
    text_content = build_contact_email_text(first_name, last_name, email, subject, message)

    email_payload = {
        "from": from_address,
        "to": [to_address],
        "reply_to": email,
        "subject": f"[Patty Project Contact] {subject}",
        "html": html_content,
        "text": text_content,
    }

    # If no API key is set in development/testing, simulate safe delivery
    if not api_key:
        if settings.is_production:
            logger.error("Contact email failed: RESEND_API_KEY is missing in production environment.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery service is currently unavailable. Please try again later."
            )
        logger.info("Dev/Test Mode: RESEND_API_KEY not set. Contact email simulated successfully to %s", to_address)
        return True

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("Contact form submission received for: %s (subject: %s)", email, subject)

    try:
        if client:
            resp = client.post(RESEND_API_URL, json=email_payload, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as http_client:
                resp = http_client.post(RESEND_API_URL, json=email_payload, headers=headers)

        if resp.status_code in (200, 201):
            logger.info("Contact email successfully sent via Resend to %s", to_address)
            return True

        # Handle provider 4xx / 5xx error
        logger.error(
            "Contact email provider failed with HTTP status %d: %s",
            resp.status_code,
            resp.text[:200]  # truncate error log to avoid leaking sensitive provider responses
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to deliver your message at this time. Please try again later."
        )

    except httpx.TimeoutException:
        logger.error("Contact email provider request timed out after %.1f seconds.", DEFAULT_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Email service timed out. Please try again in a few moments."
        )
    except httpx.RequestError as exc:
        logger.error("Contact email network connection error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Network error connecting to email service. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error during contact email transmission: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your request. Please try again."
        )


def build_verification_otp_html(otp: str) -> str:
    """Builds a secure, branded HTML email for Patty Project loyalty account email verification."""
    safe_otp = html.escape(otp)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verify your Patty Project account</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0c0c0c; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #ffffff;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0c0c0c; padding: 30px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" max-width="540" style="max-width: 540px; background-color: #141414; border: 1px solid #262626; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.8);">
          <!-- Header with Brand Accent -->
          <tr>
            <td style="background-color: #1a1a1a; padding: 28px 32px; border-bottom: 2px solid #FF5500; text-align: center;">
              <span style="font-size: 12px; font-weight: 900; color: #FF5500; letter-spacing: 3px; text-transform: uppercase;">PATTY PROJECT UK</span>
              <h1 style="margin: 8px 0 0 0; font-size: 24px; font-weight: 900; color: #ffffff; text-transform: uppercase; letter-spacing: 0.5px;">Verify Your Account</h1>
            </td>
          </tr>

          <!-- Content Body -->
          <tr>
            <td style="padding: 36px 32px; text-align: center;">
              <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6; color: #e5e5e5;">
                Your Patty Project verification code is:
              </p>

              <!-- OTP Code Display Card -->
              <div style="background-color: #0e0e0e; border: 2px dashed #FF5500; border-radius: 12px; padding: 20px; margin: 0 auto 24px auto; max-width: 320px;">
                <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 900; letter-spacing: 8px; color: #FF5500; display: inline-block;">
                  {safe_otp}
                </span>
              </div>

              <!-- Expiry Alert -->
              <div style="display: inline-block; padding: 8px 16px; background-color: #1f1a14; border: 1px solid #7c3a00; border-radius: 20px; margin-bottom: 24px;">
                <span style="font-size: 13px; font-weight: 700; color: #f59e0b;">⏱ This code expires in 10 minutes.</span>
              </div>

              <!-- Security Notice -->
              <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #888888;">
                If you did not create this account, you can ignore this email.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0e0e0e; border-top: 1px solid #222222; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #666666;">
                Patty Project UK — Artisan Smashed Burgers & Loyalty Rewards
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_verification_otp_text(otp: str) -> str:
    """Builds a plain-text version of the OTP verification email."""
    return f"""Verify your Patty Project account
==================================================

Your Patty Project verification code is:

{otp}

This code expires in 10 minutes.

If you did not create this account, you can ignore this email.

Patty Project UK
"""


def send_verification_otp_email(
    to_email: str,
    otp: str,
    client: Optional[httpx.Client] = None,
) -> bool:
    """
    Sends a 6-digit OTP verification email through Resend to the customer's submitted email.

    Security & Reliability:
    - Never exposes or logs raw OTP.
    - Never logs RESEND_API_KEY.
    - Times out safely if Resend is unreachable.
    """
    to_clean = to_email.strip().lower()
    from_address = settings.CONTACT_EMAIL_FROM or "Patty Project <website@pattyproject.co.uk>"
    api_key = settings.RESEND_API_KEY

    html_content = build_verification_otp_html(otp)
    text_content = build_verification_otp_text(otp)

    email_payload = {
        "from": from_address,
        "to": [to_clean],
        "subject": "Verify your Patty Project account",
        "html": html_content,
        "text": text_content,
    }

    # If no API key is configured in dev/test, simulate delivery
    if not api_key:
        if settings.is_production:
            logger.error("OTP verification email failed: RESEND_API_KEY is missing in production environment.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery service is currently unavailable. Please try again later."
            )
        logger.info("Dev/Test Mode: RESEND_API_KEY not set. OTP verification email simulated to %s", to_clean)
        return True

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("Dispatching OTP verification email for account: %s", to_clean)

    try:
        if client:
            resp = client.post(RESEND_API_URL, json=email_payload, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as http_client:
                resp = http_client.post(RESEND_API_URL, json=email_payload, headers=headers)

        if resp.status_code in (200, 201):
            logger.info("OTP verification email delivered via Resend to %s", to_clean)
            return True

        logger.error(
            "OTP verification email provider failed with HTTP status %d: %s",
            resp.status_code,
            resp.text[:200]
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to deliver your verification code at this time. Please try again later."
        )

    except httpx.TimeoutException:
        logger.error("OTP verification email provider request timed out after %.1f seconds.", DEFAULT_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service timed out. Please try again in a few moments."
        )
    except httpx.RequestError as exc:
        logger.error("OTP verification email network connection error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Network error connecting to email service. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error during OTP email transmission: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while sending your verification code. Please try again."
        )


def build_password_reset_html(reset_url: str) -> str:
    """Builds a secure, branded HTML email for Patty Project account password reset."""
    safe_reset_url = html.escape(reset_url)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset your Patty Project password</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0c0c0c; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #ffffff;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0c0c0c; padding: 30px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" max-width="540" style="max-width: 540px; background-color: #141414; border: 1px solid #262626; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.8);">
          <!-- Header with Brand Accent -->
          <tr>
            <td style="background-color: #1a1a1a; padding: 28px 32px; border-bottom: 2px solid #FF5500; text-align: center;">
              <span style="font-size: 12px; font-weight: 900; color: #FF5500; letter-spacing: 3px; text-transform: uppercase;">PATTY PROJECT UK</span>
              <h1 style="margin: 8px 0 0 0; font-size: 22px; font-weight: 900; color: #ffffff; text-transform: uppercase; letter-spacing: 0.5px;">Password Reset Request</h1>
            </td>
          </tr>

          <!-- Content Body -->
          <tr>
            <td style="padding: 36px 32px; text-align: center;">
              <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6; color: #e5e5e5;">
                We received a request to reset your Patty Project account password. Click the button below to choose a new password:
              </p>

              <!-- Reset Action Button -->
              <div style="margin: 28px 0 24px 0;">
                <a href="{safe_reset_url}" style="background-color: #FF5500; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 800; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; display: inline-block; box-shadow: 0 4px 14px rgba(255, 85, 0, 0.4);">
                  Reset Password
                </a>
              </div>

              <!-- Expiry Alert -->
              <div style="display: inline-block; padding: 8px 16px; background-color: #1f1a14; border: 1px solid #7c3a00; border-radius: 20px; margin-bottom: 24px;">
                <span style="font-size: 13px; font-weight: 700; color: #f59e0b;">⏱ This link expires in 30 minutes and can only be used once.</span>
              </div>

              <!-- Fallback Direct URL -->
              <p style="margin: 0 0 20px 0; font-size: 12px; line-height: 1.5; color: #888888;">
                If the button above does not work, copy and paste the following link into your browser:<br/>
                <span style="color: #FF5500; word-break: break-all;">{safe_reset_url}</span>
              </p>

              <!-- Security Notice -->
              <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #71717A; border-top: 1px solid #242424; padding-top: 20px;">
                If you did not request this password reset, you can safely ignore this email. Your password will remain unchanged.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #0e0e0e; border-top: 1px solid #222222; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #666666;">
                Patty Project UK — Artisan Smashed Burgers & Loyalty Rewards
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_password_reset_text(reset_url: str) -> str:
    """Builds a plain-text version of the password reset email."""
    return f"""Reset your Patty Project password
==================================================

We received a request to reset your Patty Project account password.

To set a new password, open this link in your browser:
{reset_url}

This link expires in 30 minutes and can only be used once.

If you did not request this reset, you can safely ignore this email. Your password will remain unchanged.

Patty Project UK
"""


def send_password_reset_email(
    to_email: str,
    reset_url: str,
    client: Optional[httpx.Client] = None,
) -> bool:
    """
    Sends a password reset link email through Resend to the customer's verified email.

    Security & Privacy:
    - Never logs the raw reset URL or token.
    - Never logs RESEND_API_KEY.
    - Times out safely if Resend is unreachable.
    """
    to_clean = to_email.strip().lower()
    from_address = settings.CONTACT_EMAIL_FROM or "Patty Project <website@pattyproject.co.uk>"
    api_key = settings.RESEND_API_KEY

    html_content = build_password_reset_html(reset_url)
    text_content = build_password_reset_text(reset_url)

    email_payload = {
        "from": from_address,
        "to": [to_clean],
        "subject": "Reset your Patty Project password",
        "html": html_content,
        "text": text_content,
    }

    # If no API key is configured in dev/test, simulate delivery
    if not api_key:
        if settings.is_production:
            logger.error("Password reset email failed: RESEND_API_KEY is missing in production environment.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery service is currently unavailable. Please try again later."
            )
        logger.info("Dev/Test Mode: RESEND_API_KEY not set. Password reset email simulated to %s", to_clean)
        return True

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("Dispatching password reset email for account: %s", to_clean)

    try:
        if client:
            resp = client.post(RESEND_API_URL, json=email_payload, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as http_client:
                resp = http_client.post(RESEND_API_URL, json=email_payload, headers=headers)

        if resp.status_code in (200, 201):
            logger.info("Password reset email delivered via Resend to %s", to_clean)
            return True

        logger.error(
            "Password reset email provider failed with HTTP status %d: %s",
            resp.status_code,
            resp.text[:200]
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to deliver your password reset email at this time. Please try again later."
        )

    except httpx.TimeoutException:
        logger.error("Password reset email provider request timed out after %.1f seconds.", DEFAULT_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service timed out. Please try again in a few moments."
        )
    except httpx.RequestError as exc:
        logger.error("Password reset email network connection error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Network error connecting to email service. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error during password reset email transmission: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while sending your password reset email. Please try again."
        )
