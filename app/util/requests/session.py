# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override

from requests import Session
from requests.adapters import HTTPAdapter
from requests_cache import CachedResponse, CacheMixin, OriginalResponse
from requests_ratelimiter import LimiterAdapter, LimiterMixin


class CustomSession(CacheMixin, LimiterMixin, Session):  # pyright: ignore [reportIncompatibleMethodOverride] as this is caused by the mixins which are in library code we do not control
    """Custom session class that includes caching and rate limiting capabilities by default."""

    def __init__(self, *args, **kwargs) -> None:
        from .manager import RequestsManager

        self._requests_manager = RequestsManager()
        self._requests_config = self._requests_manager.config
        if self._requests_config is None:
            msg = "RequestsManager must be initialized before using CustomSession"
            raise RuntimeError(msg)

        # Initialize the rate limiter if not already done
        if "limiter" not in kwargs:
            kwargs["limiter"] = self._requests_config.rate_limit.limiter

        super().__init__(*args, **kwargs)

        # Per-host rate limits
        for host, rate_config in self._requests_config.rate_limit.hosts.items():
            adapter = HTTPAdapter() if rate_config is None else LimiterAdapter(limiter=rate_config.limiter)
            self.mount(f"http://{host}/", adapter)
            self.mount(f"https://{host}/", adapter)

    @override
    def request(self, *args, **kwargs) -> OriginalResponse | CachedResponse:
        kwargs.setdefault("timeout", self._requests_config.timeout)
        return super().request(*args, **kwargs)
