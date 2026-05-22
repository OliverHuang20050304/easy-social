from __future__ import annotations

import re

import pytest

from easy_social.captcha import (
    SESSION_ANSWER_KEY,
    clear_challenge,
    generate_challenge,
    verify_response,
)

pytestmark = pytest.mark.unit


def test_generate_challenge_stores_answer_in_session():
    session: dict[str, int | str] = {}

    question = generate_challenge(session)

    assert re.fullmatch(r"\d+ \+ \d+ = \?", question)
    assert SESSION_ANSWER_KEY in session
    left, right = map(int, question.replace(" = ?", "").split(" + "))
    assert session[SESSION_ANSWER_KEY] == left + right


def test_verify_response_accepts_correct_answer():
    session = {SESSION_ANSWER_KEY: 8}

    assert verify_response(session, "8") is True
    assert SESSION_ANSWER_KEY not in session


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("9", False),
        ("", False),
        ("abc", False),
    ],
)
def test_verify_response_rejects_invalid_answers(response: str, expected: bool):
    session = {SESSION_ANSWER_KEY: 8}

    assert verify_response(session, response) is expected
    assert SESSION_ANSWER_KEY not in session


def test_verify_response_without_session_answer_fails():
    assert verify_response({}, "8") is False


def test_clear_challenge_removes_session_answer():
    session = {SESSION_ANSWER_KEY: 8}

    clear_challenge(session)

    assert SESSION_ANSWER_KEY not in session
