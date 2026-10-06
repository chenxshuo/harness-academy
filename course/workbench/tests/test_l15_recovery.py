"""Level 15 - failure classification and retry."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_rate_limit_is_transient():
    from recovery import TRANSIENT, classify_error

    assert classify_error(429, "rate limit exceeded") == TRANSIENT


def test_server_error_is_transient():
    from recovery import TRANSIENT, classify_error

    assert classify_error(500, "internal error") == TRANSIENT
    assert classify_error(503, "unavailable") == TRANSIENT


def test_auth_failure_is_terminal():
    """Waiting will not make a bad key good."""
    from recovery import TERMINAL, classify_error

    assert classify_error(401, "invalid api key") == TERMINAL


def test_malformed_request_is_terminal():
    from recovery import TERMINAL, classify_error

    assert classify_error(400, "tool_use ids were found without tool_result blocks") == TERMINAL


def test_context_overflow_is_its_own_category():
    """Deterministic, yet recoverable - by compacting, not by retrying."""
    from recovery import OVERFLOW, classify_error

    assert classify_error(400, "prompt is too long: 213041 tokens > 200000 maximum") == OVERFLOW
    assert classify_error(400, "maximum context length exceeded") == OVERFLOW


def test_backoff_grows_and_is_capped():
    from recovery import retry_delay

    assert retry_delay(0) < retry_delay(1) < retry_delay(2), "backoff must grow"
    assert retry_delay(20, max_delay=8.0) <= 8.0, (
        "uncapped exponential backoff eventually means a user waiting minutes "
        "for a request they would rather see fail"
    )


async def test_transient_failures_are_retried():
    from recovery import ProviderError, with_retry

    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise ProviderError(429, "slow down")
        return "ok"

    result = await with_retry(flaky, max_retries=3, max_delay=0.01)

    assert result == "ok"
    assert len(attempts) == 3, f"expected 3 attempts, got {len(attempts)}"


async def test_terminal_failures_are_not_retried():
    from recovery import ProviderError, with_retry

    attempts = []

    async def broken():
        attempts.append(1)
        raise ProviderError(401, "invalid api key")

    with pytest.raises(ProviderError):
        await with_retry(broken, max_retries=3, max_delay=0.01)

    assert len(attempts) == 1, (
        f"a terminal error was attempted {len(attempts)} times. It must raise "
        f"immediately - a 401 that takes 30s to report is worse than one that "
        f"fails instantly."
    )


async def test_retry_progress_is_reported():
    """A silent retry looks like a hang."""
    from recovery import ProviderError, with_retry

    seen = []

    async def flaky():
        if len(seen) < 1:
            raise ProviderError(429, "slow down")
        return "ok"

    await with_retry(
        flaky,
        max_retries=2,
        max_delay=0.01,
        on_retry=lambda attempt, delay, reason: seen.append((attempt, reason)),
    )

    assert seen, (
        "on_retry must be called before waiting, so a frontend can show what "
        "is happening instead of appearing frozen"
    )


async def test_exhausting_retries_raises_the_last_error():
    from recovery import ProviderError, with_retry

    async def always_down():
        raise ProviderError(503, "unavailable")

    with pytest.raises(ProviderError):
        await with_retry(always_down, max_retries=2, max_delay=0.01)
