"""Email service using Resend for transactional emails."""

import logging
from config import get_settings

logger = logging.getLogger(__name__)


def send_invite_email(
    to_email: str,
    workspace_name: str,
    inviter_email: str,
    invite_token: str,
    role: str,
) -> bool:
    """
    Send a workspace invite email via Resend.
    Returns True on success, False on failure.
    Never raises — callers should not fail if email delivery fails.
    """
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping invite email to %s", to_email)
        return False

    invite_url = f"{settings.app_url}/invites/{invite_token}"

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 40px 20px;">
      <h2 style="color: #1a1a1a; margin-bottom: 8px;">You're invited to join a workspace</h2>
      <p style="color: #555; font-size: 15px; line-height: 1.6;">
        <strong>{inviter_email}</strong> has invited you to join
        <strong>{workspace_name}</strong> as a <strong>{role}</strong>.
      </p>
      <a href="{invite_url}"
         style="display: inline-block; background: #2563eb; color: #fff; padding: 12px 28px;
                border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;
                margin: 24px 0;">
        Accept Invitation
      </a>
      <p style="color: #888; font-size: 13px; margin-top: 32px;">
        This invitation expires in 7 days. If you didn't expect this email, you can safely ignore it.
      </p>
    </div>
    """

    try:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": f"You're invited to {workspace_name} on OPPM",
            "html": html,
        })
        logger.info("Invite email sent to %s for workspace %s", to_email, workspace_name)
        return True
    except Exception as e:
        logger.error("Failed to send invite email to %s: %s", to_email, e)
        return False
