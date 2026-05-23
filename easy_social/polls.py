from __future__ import annotations

MIN_POLL_OPTIONS = 2
MAX_POLL_OPTIONS = 4


def normalize_poll_options(raw_options: list[str]) -> list[str]:
    """Strip whitespace and drop empty option strings."""
    return [option.strip() for option in raw_options if option.strip()]


def validate_poll_options(raw_options: list[str]) -> list[str]:
    """Validate poll option labels and return the normalized list.

    Args:
        raw_options: Raw option strings from a form submission.

    Returns:
        A list of non-empty option labels.

    Raises:
        ValueError: If the option count or any option text is invalid.
    """
    options = normalize_poll_options(raw_options)
    if len(options) < MIN_POLL_OPTIONS:
        raise ValueError(f"A poll needs at least {MIN_POLL_OPTIONS} options.")
    if len(options) > MAX_POLL_OPTIONS:
        raise ValueError(f"A poll can have at most {MAX_POLL_OPTIONS} options.")
    if len(options) != len(set(option.casefold() for option in options)):
        raise ValueError("Poll options must be unique.")
    return options


def option_percentages(vote_counts: list[int]) -> list[float]:
    """Calculate each option's share of votes as a percentage.

    Args:
        vote_counts: Vote totals per option in display order.

    Returns:
        Percentages that sum to 100.0 when there is at least one vote,
        otherwise zeros.
    """
    total_votes = sum(vote_counts)
    if total_votes == 0:
        return [0.0 for _ in vote_counts]
    return [round((count / total_votes) * 100, 1) for count in vote_counts]
