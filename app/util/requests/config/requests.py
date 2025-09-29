# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import Field

from ...config.models import BaseConfigModel
from .cache import RequestCacheConfig
from .rate import DefaultRequestRateConfig


# MARK: Requests Configuration
class RequestsConfig(BaseConfigModel):
    cache: RequestCacheConfig = Field(default_factory=RequestCacheConfig, description="Configuration for the requests cache.")

    rate_limit: DefaultRequestRateConfig = Field(
        default_factory=lambda: DefaultRequestRateConfig(limit=1, interval=1), description="Rate limit configuration for requests."
    )

    timeout: int = Field(default=10, description="Timeout for network requests in seconds")
