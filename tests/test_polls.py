from __future__ import annotations

import pytest

from easy_social.polls import option_percentages, validate_poll_options

pytestmark = pytest.mark.unit


def test_validate_poll_options_accepts_two_to_four_unique_options():
    assert validate_poll_options(["Red", "Blue"]) == ["Red", "Blue"]
    assert validate_poll_options([" A ", "B", " C ", "D"]) == ["A", "B", "C", "D"]


def test_validate_poll_options_rejects_too_few_options():
    with pytest.raises(ValueError, match="at least 2"):
        validate_poll_options(["Only one"])


def test_validate_poll_options_rejects_too_many_options():
    with pytest.raises(ValueError, match="at most 4"):
        validate_poll_options(["1", "2", "3", "4", "5"])


def test_validate_poll_options_rejects_blank_options():
    with pytest.raises(ValueError, match="at least 2"):
        validate_poll_options(["Valid", "   "])


def test_validate_poll_options_rejects_duplicate_options():
    with pytest.raises(ValueError, match="unique"):
        validate_poll_options(["Same", "same"])


@pytest.mark.parametrize(
    ("vote_counts", "expected"),
    [
        ([2, 1, 1], [50.0, 25.0, 25.0]),
        ([0, 0], [0.0, 0.0]),
        ([1], [100.0]),
    ],
)
def test_option_percentages(vote_counts: list[int], expected: list[float]):
    assert option_percentages(vote_counts) == expected
