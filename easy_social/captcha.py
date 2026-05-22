from __future__ import annotations

import random
import secrets
from typing import Any

from flask import current_app

SESSION_CHALLENGE_KEY = "captcha_challenge_id"
CONFIG_STORE_KEY = "CAPTCHA_STORE"


class CaptchaStore:
    """Server-side in-memory CAPTCHA answer store.

    This is a simplified teaching/demo implementation. Production deployments
    should use a shared persistent store such as Redis or the database so
    answers survive restarts and work across multiple app processes.
    """

    def __init__(self) -> None:
        self._answers: dict[str, int] = {}

    def create(self, answer: int) -> str:
        challenge_id = secrets.token_urlsafe(16)
        self._answers[challenge_id] = answer
        return challenge_id

    def pop(self, challenge_id: str) -> int | None:
        return self._answers.pop(challenge_id, None)

    def clear(self, challenge_id: str) -> None:
        self._answers.pop(challenge_id, None)


def get_store() -> CaptchaStore:
    store = current_app.config.get(CONFIG_STORE_KEY)
    if store is None:
        store = CaptchaStore()
        current_app.config[CONFIG_STORE_KEY] = store
    return store


def _clear_session_challenge(session: dict[str, Any], store: CaptchaStore) -> None:
    challenge_id = session.pop(SESSION_CHALLENGE_KEY, None)
    if challenge_id:
        store.clear(challenge_id)


def generate_challenge(session: dict[str, Any]) -> str:
    """Generate a math CAPTCHA and bind it to a server-side challenge token."""
    left = random.randint(1, 9)
    right = random.randint(1, 9)
    answer = left + right
    store = get_store()
    _clear_session_challenge(session, store)
    challenge_id = store.create(answer)
    session[SESSION_CHALLENGE_KEY] = challenge_id
    return f"{left} + {right} = ?"


def verify_response(session: dict[str, Any], response: str) -> bool:
    """Verify the submitted answer against the server-side challenge store."""
    challenge_id = session.pop(SESSION_CHALLENGE_KEY, None)
    if not challenge_id:
        return False

    store = get_store()
    expected = store.pop(challenge_id)
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
    """Remove the active challenge token and its server-side answer."""
    _clear_session_challenge(session, get_store())
