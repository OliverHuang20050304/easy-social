from __future__ import annotations

import random
from typing import Any

SESSION_ANSWER_KEY = "captcha_answer"


def generate_challenge(session: dict[str, Any]) -> str:
    """Generate a math CAPTCHA question and store the answer in the session."""
    left = random.randint(1, 9)
    right = random.randint(1, 9)
    session[SESSION_ANSWER_KEY] = left + right
    return f"{left} + {right} = ?"


def verify_response(session: dict[str, Any], response: str) -> bool:
    """Return True when the submitted answer matches the session value."""
    expected = session.pop(SESSION_ANSWER_KEY, None)
    if expected is None:
        return False

    value = response.strip()
    if not value:
        return False

    try:
        return int(value) == int(expected)
    except ValueError:
        return False


def clear_challenge(session: dict[str, Any]) -> None:
    """Remove any stored CAPTCHA answer from the session."""
    session.pop(SESSION_ANSWER_KEY, None)
