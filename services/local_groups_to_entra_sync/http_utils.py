"""Shared HTTP utility helpers for Graph API calls."""

import logging
import time
from typing import Callable

import requests

from .config import RETRY_BACKOFF_SECONDS, RETRY_COUNT

logger = logging.getLogger(__name__)


def post_with_retry(
    url: str,
    payload: dict,
    headers: dict,
    retry_on_status: set[int],
    context: str = "",
    retries: int = RETRY_COUNT,
    backoff: float = RETRY_BACKOFF_SECONDS,
    success_check: Callable[[requests.Response], bool] | None = None,
    noop_check: Callable[[requests.Response], bool] | None = None,
) -> requests.Response:
    """POST to a URL, retrying when the response status is in ``retry_on_status``.

    Args:
        url:              Target URL.
        payload:          JSON body.
        headers:          HTTP headers (including Authorization).
        retry_on_status:  Set of HTTP status codes that should trigger a retry.
        context:          Human-readable label used in log messages.
        retries:          Maximum number of attempts.
        backoff:          Base backoff in seconds; wait = backoff * attempt.
        success_check:    Optional callable(response) -> bool. If provided and
                          returns True the response is returned immediately
                          without calling raise_for_status.
        noop_check:       Optional callable(response) -> bool. If provided and
                          returns True the response is returned immediately as a
                          no-op (e.g. "already exists").

    Returns:
        The final requests.Response object.

    Raises:
        requests.HTTPError: On a non-retryable error or after all retries are
                            exhausted.
    """
    for attempt in range(1, retries + 1):
        response = requests.post(url, json=payload, headers=headers)
        logger.debug(
            "POST %s status=%d (attempt %d/%d) context=%s",
            url, response.status_code, attempt, retries, context,
        )

        # Caller-defined success condition (e.g. 204 No Content)
        if success_check and success_check(response):
            return response

        # Caller-defined no-op condition (e.g. duplicate member)
        if noop_check and noop_check(response):
            return response

        # Retryable status — wait and try again
        if response.status_code in retry_on_status and attempt < retries:
            wait = backoff * attempt
            logger.warning(
                "Retryable status %d for %s, retrying in %.1fs (attempt %d/%d)",
                response.status_code, context, wait, attempt, retries,
            )
            time.sleep(wait)
            continue

        response.raise_for_status()
        return response

    # Should be unreachable — last raise_for_status covers it
    raise RuntimeError(f"post_with_retry exhausted all attempts for {context}")
