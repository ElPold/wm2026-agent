"""Gemeinsamer HTTP-Client mit einfachem Rate-Limiting."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HttpClient:
    def __init__(
        self,
        min_interval_sec: float = 1.0,
        timeout_sec: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries
        self._last_request_at = 0.0
        self._session = requests.Session()

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        last_error: ApiError | None = None

        for attempt in range(self._max_retries + 1):
            self._respect_rate_limit()
            try:
                response = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self._timeout_sec,
                )
            except requests.RequestException as exc:
                if attempt >= self._max_retries:
                    raise ApiError(f"HTTP-Anfrage fehlgeschlagen: {exc}") from exc
                wait_sec = min(2**attempt, 30)
                logger.warning(
                    "HTTP-Anfrage fehlgeschlagen (%s), Retry in %s s (%d/%d)",
                    exc,
                    wait_sec,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(wait_sec)
                continue

            self._last_request_at = time.monotonic()

            if response.status_code == 429:
                if attempt >= self._max_retries:
                    raise ApiError(
                        "Rate limit erreicht — maximale Retries überschritten",
                        status_code=429,
                    )
                retry_after = response.headers.get("Retry-After")
                wait_sec = float(retry_after) if retry_after else min(2**attempt, 30)
                logger.warning(
                    "Rate limit erreicht, warte %s s (%d/%d)",
                    wait_sec,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(wait_sec)
                continue

            if response.status_code >= 500:
                last_error = ApiError(
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    status_code=response.status_code,
                )
                if attempt >= self._max_retries:
                    raise last_error
                wait_sec = min(2**attempt, 30)
                logger.warning(
                    "Serverfehler %s, Retry in %s s (%d/%d)",
                    response.status_code,
                    wait_sec,
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(wait_sec)
                continue

            if not response.ok:
                raise ApiError(
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    status_code=response.status_code,
                )

            return response.json()

        if last_error:
            raise last_error
        raise ApiError("HTTP-Anfrage fehlgeschlagen")

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
