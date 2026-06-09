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
    def __init__(self, min_interval_sec: float = 1.0, timeout_sec: float = 30.0) -> None:
        self._min_interval_sec = min_interval_sec
        self._timeout_sec = timeout_sec
        self._last_request_at = 0.0
        self._session = requests.Session()

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        self._respect_rate_limit()
        response = self._session.get(
            url,
            params=params,
            headers=headers,
            timeout=self._timeout_sec,
        )
        self._last_request_at = time.monotonic()

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "2")
            logger.warning("Rate limit erreicht, warte %s s", retry_after)
            time.sleep(float(retry_after))
            return self.get_json(url, params=params, headers=headers)

        if not response.ok:
            raise ApiError(
                f"HTTP {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
            )

        return response.json()

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval_sec:
            time.sleep(self._min_interval_sec - elapsed)
