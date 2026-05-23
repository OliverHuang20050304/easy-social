from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from .extensions import db
from .models import CaptchaChallenge, _as_utc_naive, _utc_now_naive

SESSION_CHALLENGE_KEY = "captcha_challenge_id"
DEFAULT_CAPTCHA_TTL = timedelta(minutes=5)


def purge_expired_challenges() -> None:
    """Delete CAPTCHA challenges that have passed their expiration time."""
    now = _utc_now_naive()
    expired_ids = [
        challenge.challenge_id
        for challenge in CaptchaChallenge.query.all()
        if _as_utc_naive(challenge.expires_at) < now
    ]
    if expired_ids:
        CaptchaChallenge.query.filter(
            CaptchaChallenge.challenge_id.in_(expired_ids)
        ).delete(synchronize_session=False)
        db.session.commit()


def _delete_challenge(challenge_id: str | None) -> None:
    if not challenge_id:
        return
    challenge = db.session.get(CaptchaChallenge, challenge_id)
    if challenge is not None:
        db.session.delete(challenge)
        db.session.commit()


def _clear_session_challenge(session: dict[str, Any]) -> None:
    challenge_id = session.pop(SESSION_CHALLENGE_KEY, None)
    _delete_challenge(challenge_id)


def _consume_challenge(challenge_id: str) -> int | None:
    """Load, delete, and return the answer when the challenge is still valid."""
    challenge = db.session.get(CaptchaChallenge, challenge_id)
    if challenge is None:
        return None

    answer = challenge.answer
    expired = challenge.is_expired
    db.session.delete(challenge)
    db.session.commit()

    if expired:
        return None
    return answer


def generate_challenge(session: dict[str, Any]) -> str:
    """Generate a math CAPTCHA and bind it to a database-backed challenge token."""
    purge_expired_challenges()
    _clear_session_challenge(session)

    left = random.randint(1, 9)
    right = random.randint(1, 9)
    answer = left + right
    challenge = CaptchaChallenge.create_challenge(answer, ttl=DEFAULT_CAPTCHA_TTL)
    session[SESSION_CHALLENGE_KEY] = challenge.challenge_id
    return f"{left} + {right} = ?"


def verify_response(session: dict[str, Any], response: str) -> bool:
    """Verify the submitted answer against the shared database challenge store."""
    challenge_id = session.pop(SESSION_CHALLENGE_KEY, None)
    if not challenge_id:
        return False

    expected = _consume_challenge(challenge_id)
    if expected is None:
        return False

    value = response.strip()
    if not value:
        return False

    try:
        return int(value) == expected
    except ValueError:
        return False


def clear_challenge(session: dict[str, Any]) -> None:
    """Remove the active challenge token and its database record."""
    _clear_session_challenge(session)
