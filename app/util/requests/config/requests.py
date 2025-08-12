# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from .cache import RequestCacheConfig, RequestsCacheBackend, RequestsCacheRootDir
from .rate import DefaultRequestRateConfig

from ...config.models import BaseConfigModel

from pydantic import Field


# MARK: Requests Configuration
class RequestsConfig(BaseConfigModel):
    cache : RequestCacheConfig = Field(default_factory=RequestCacheConfig, description='Configuration for the requests cache.')
    rate_limit : DefaultRequestRateConfig = Field(default_factory=lambda: DefaultRequestRateConfig(limit=1, interval=10), description='Rate limit configuration for requests.')