from __future__ import annotations

import re
from datetime import timedelta

import pytest
from flask import session

from easy_social.captcha import (
    SESSION_CHALLENGE_KEY,
    clear_challenge,
    generate_challenge,
    purge_expired_challenges,
    verify_response,
)
from easy_social.extensions import db
from easy_social.models import CaptchaChallenge, _utc_now_naive

pytestmark = pytest.mark.unit


def test_generate_challenge_stores_token_in_session_and_answer_in_database(app):
    with app.app_context():
        with app.test_request_context():
            question = generate_challenge(session)

            assert re.fullmatch(r"\d+ \+ \d+ = \?", question)
            assert SESSION_CHALLENGE_KEY in session
            assert "captcha_answer" not in session

            challenge_id = session[SESSION_CHALLENGE_KEY]
            left, right = map(int, question.replace(" = ?", "").split(" + "))
            challenge = db.session.get(CaptchaChallenge, challenge_id)
            assert challenge is not None
            assert challenge.answer == left + right


def test_verify_response_accepts_correct_answer(app):
    with app.app_context():
        challenge = CaptchaChallenge.create_challenge(8)

        with app.test_request_context() as ctx:
            ctx.session[SESSION_CHALLENGE_KEY] = challenge.challenge_id
            assert verify_response(session, "8") is True
            assert SESSION_CHALLENGE_KEY not in session
            assert db.session.get(CaptchaChallenge, challenge.challenge_id) is None


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("9", False),
        ("", False),
        ("abc", False),
    ],
)
def test_verify_response_rejects_invalid_answers(app, response: str, expected: bool):
    with app.app_context():
        challenge = CaptchaChallenge.create_challenge(8)

        with app.test_request_context() as ctx:
            ctx.session[SESSION_CHALLENGE_KEY] = challenge.challenge_id
            assert verify_response(session, response) is expected
            assert SESSION_CHALLENGE_KEY not in session
            assert db.session.get(CaptchaChallenge, challenge.challenge_id) is None


def test_verify_response_without_session_token_fails(app):
    with app.app_context():
        with app.test_request_context():
            assert verify_response(session, "8") is False


def test_verify_response_rejects_expired_challenge(app):
    with app.app_context():
        challenge = CaptchaChallenge.create_challenge(8)
        challenge.expires_at = _utc_now_naive() - timedelta(seconds=1)
        db.session.commit()

        with app.test_request_context() as ctx:
            ctx.session[SESSION_CHALLENGE_KEY] = challenge.challenge_id
            assert verify_response(session, "8") is False
            assert db.session.get(CaptchaChallenge, challenge.challenge_id) is None


def test_challenge_cannot_be_reused_after_successful_verification(app):
    with app.app_context():
        challenge = CaptchaChallenge.create_challenge(8)
        challenge_id = challenge.challenge_id

        with app.test_request_context() as ctx:
            ctx.session[SESSION_CHALLENGE_KEY] = challenge_id
            assert verify_response(session, "8") is True
            ctx.session[SESSION_CHALLENGE_KEY] = challenge_id
            assert verify_response(session, "8") is False


def test_purge_expired_challenges_removes_only_expired_rows(app):
    with app.app_context():
        active = CaptchaChallenge.create_challenge(3)
        expired = CaptchaChallenge.create_challenge(5)
        expired_id = expired.challenge_id
        expired.expires_at = _utc_now_naive() - timedelta(seconds=1)
        db.session.commit()

        purge_expired_challenges()

        assert db.session.get(CaptchaChallenge, active.challenge_id) is not None
        assert db.session.get(CaptchaChallenge, expired_id) is None


def test_clear_challenge_removes_token_and_database_row(app):
    with app.app_context():
        challenge = CaptchaChallenge.create_challenge(8)

        with app.test_request_context() as ctx:
            ctx.session[SESSION_CHALLENGE_KEY] = challenge.challenge_id
            clear_challenge(session)

            assert SESSION_CHALLENGE_KEY not in session
            assert db.session.get(CaptchaChallenge, challenge.challenge_id) is None
