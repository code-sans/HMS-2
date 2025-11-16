import logging

logger = logging.getLogger(__name__)


def send_email(to_email, subject, body):
    """Stubbed email sender — replace with SMTP or third-party API in production."""
    logger.info("Sending email to %s: %s", to_email, subject)
    # For now just log; real implementation would use SMTP or service API
    print(f"[EMAIL] To: {to_email}\nSubject: {subject}\n{body}\n")


def send_webhook(url, payload):
    """Send a webhook (HTTP POST). Keep simple; no retries here."""
    logger.info("Sending webhook to %s", url)
    try:
        import requests

        resp = requests.post(url, json=payload, timeout=10)
        logger.info("Webhook status: %s", resp.status_code)
    except Exception as e:
        logger.exception("Webhook send failed: %s", e)


def notify_user(user_email, subject, body):
    # Convenience wrapper: currently uses email. Could expand to SMS/Webhook mapping.
    send_email(user_email, subject, body)
