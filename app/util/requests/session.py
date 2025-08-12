# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from requests import Session
from requests.adapters import HTTPAdapter
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterMixin, LimiterAdapter

import logging


class CustomSession(CacheMixin, LimiterMixin, Session): # pyright: ignore [reportIncompatibleMethodOverride] as this is caused by the mixins which are in library code we do not control
    """
    Custom session class that includes caching and rate limiting capabilities by default.
    """

    def __init__(self, *args, **kwargs):
        from .manager import RequestsManager
        self._requests_config = RequestsManager().config
        if self._requests_config is None:
            raise RuntimeError("RequestsManager must be initialized before using CustomSession")

        # Initialize the rate limiter if not already done
        if 'limiter' not in kwargs:
            kwargs['limiter'] = self._requests_config.rate_limit.limiter

        super().__init__(*args, **kwargs)

        # Per-host rate limits
        for host, rate_config in self._requests_config.rate_limit.hosts.items():
            if rate_config is None:
                adapter = HTTPAdapter()
            else:
                adapter = LimiterAdapter(limiter=rate_config.limiter)
            self.mount(f'http://{host}/', adapter)
            self.mount(f'https://{host}/', adapter)
