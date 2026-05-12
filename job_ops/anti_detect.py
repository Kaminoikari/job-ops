"""Rate limiting + User-Agent rotation for 104 scraping.

合併自 GetHired.ai 的 rate_limiter.py + fingerprint.py，移除 structlog 改用 stdlib。
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Limits:
    min_delay: float = 0.5
    max_delay: float = 1.5
    hourly_limit: int = 1500   # 一次 bootstrap 回填可能需要上千 requests
    max_pages: int = 100


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]


class SessionUA:
    """Per-session sticky User-Agent。"""

    def __init__(self) -> None:
        self._ua: str | None = None

    def get(self) -> str:
        if self._ua is None:
            self._ua = random.choice(_USER_AGENTS)
        return self._ua

    def rotate(self) -> None:
        self._ua = random.choice(_USER_AGENTS)


class RateLimiter:
    """Adaptive rate limiter with circuit breaker + exponential backoff on 429."""

    def __init__(self, name: str = "104", limits: Limits | None = None):
        self._name = name
        self._limits = limits or Limits()
        self._request_times: list[float] = []
        self._consecutive_errors = 0
        self._backoff_until: float = 0.0

    @property
    def max_pages(self) -> int:
        return self._limits.max_pages

    async def wait(self) -> None:
        now = time.time()

        if self._consecutive_errors >= 5:
            log.warning("[%s] circuit breaker open (%d errors)", self._name, self._consecutive_errors)
            raise RuntimeError(f"Circuit breaker open for {self._name}")

        if now < self._backoff_until:
            wait = self._backoff_until - now
            log.info("[%s] backoff %.1fs", self._name, wait)
            await asyncio.sleep(wait)

        one_hour_ago = now - 3600
        self._request_times = [t for t in self._request_times if t > one_hour_ago]
        if len(self._request_times) >= self._limits.hourly_limit:
            wait = self._request_times[0] - one_hour_ago
            log.warning("[%s] hourly limit reached, sleeping %.1fs", self._name, wait)
            await asyncio.sleep(wait)

        delay = random.uniform(self._limits.min_delay, self._limits.max_delay)
        if random.random() < 0.05:
            delay += random.uniform(3, 10)

        await asyncio.sleep(delay)
        self._request_times.append(time.time())

    def record_success(self) -> None:
        self._consecutive_errors = 0

    def record_error(self, status_code: int | None = None) -> None:
        self._consecutive_errors += 1
        if status_code == 429:
            backoff = 30 * (2 ** min(self._consecutive_errors - 1, 3))
            self._backoff_until = time.time() + backoff
            log.warning("[%s] 429 received, backoff %.0fs", self._name, backoff)
