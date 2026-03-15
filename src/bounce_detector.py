"""Bounce detection utilities."""

from typing import List

def is_bounce_email(sender_email: str, subject: str) -> bool:
    """
    Determine if an email is a bounce/delivery notification.

    Args:
        sender_email: The email sender address
        subject: Email subject line

    Returns:
        True if this is a bounce notification that should be skipped
    """
    sender = sender_email.lower()
    subj = subject.lower() if subject else ''

    # Bounce sender patterns
    bounce_senders = [
        'mailer-daemon',
        'postmaster',
        'abuse@',
        'noreply',
        'no-reply',
        'donotreply',
        'automated',
        'bounce',
        'daemon',
        'notifications-noreply',
        'security-noreply',
        'invitation@google.com',
        'calendar-notification',
        'google.com/calendar'
    ]
    for pattern in bounce_senders:
        if pattern in sender:
            return True

    # Bounce subject patterns
    bounce_subjects = [
        'delivery status notification',
        'undeliverable',
        'returned mail',
        'mail delivery failed',
        'delivery failure',
        'bounce',
    ]
    for pattern in bounce_subjects:
        if pattern in subj:
            return True

    return False
