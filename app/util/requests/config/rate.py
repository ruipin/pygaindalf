# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from functools import cached_property

from pydantic import Field, PositiveInt
from requests_ratelimiter import Limiter, RequestRate

from ...config.models import BaseConfigModel


# MARK: Default Request Rate Configuration
class RequestRateConfig(BaseConfigModel):
    limit: PositiveInt = Field(description="Rate limit in requests per interval.")
    interval: PositiveInt = Field(default=1, description="Interval for the rate limit in seconds.")

    def to_rate(self) -> RequestRate:
        return RequestRate(limit=self.limit, interval=self.interval)

    def to_limiter(self) -> Limiter:
        return Limiter(self.to_rate())

    @cached_property
    def limiter(self) -> Limiter:
        """Returns a Limiter instance based on the rate limit configuration."""
        return self.to_limiter()


class DefaultRequestRateConfig(RequestRateConfig):
    hosts: dict[str, RequestRateConfig | None] = Field(
        default_factory=dict,
        description="Rate limits for specific hosts, where the key is the host name and the value is the rate limit configuration. If None, no rate limit is applied.",
    )
