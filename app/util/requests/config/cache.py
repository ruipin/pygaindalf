# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import os

from enum import Enum, StrEnum
from pydantic import Field, PositiveInt, model_validator
from typing import Any

from requests_ratelimiter import Duration

from ...config.models import BaseConfigModel
from ...helpers import script_info


# MARK: Enums
class RequestsCacheBackend(StrEnum):
    """
    Enum for cache backends from requests_cache we support.
    """
    SQLITE = 'sqlite'
    FILESYSTEM = 'filesystem'
    MEMORY = 'memory'

class RequestsCacheFileType(Enum):
    """
    Enum for file types used in requests_cache.
    """
    NONE = 'none'
    JSON = 'json'
    YAML = 'yaml'

class RequestsCacheRootDir(Enum):
    """
    Enum for root directories used in requests_cache.
    """
    SCRIPT_HOME = 'script_home'
    TEMP = 'temp'
    USER = 'user'


# MARK: Request Cache Configuration
class RequestCacheConfig(BaseConfigModel):
    cache_name   : str                   = Field(default='cache'                         , description='Name of the cache to be used.')
    root_dir     : RequestsCacheRootDir  = Field(default=RequestsCacheRootDir.SCRIPT_HOME, description='Root directory for the cache.')
    backend      : RequestsCacheBackend  = Field(default=RequestsCacheBackend.FILESYSTEM , description='Backend for the cache storage.')
    filetype     : RequestsCacheFileType = Field(default=RequestsCacheFileType.JSON      , description='File type for the cache storage.')
    expire_after : PositiveInt | None    = Field(default=None                            , description='Time in seconds after which the cache expires, or null to disable expiration.')
    ignored_parameters : list[str]       = Field(default_factory=list                    , description='List of user-defined parameters to ignore in cache requests.')

    @model_validator(mode='after')
    def validate_filetype(self) -> 'RequestCacheConfig':
        """
        Validate the filetype is compatible with the backend.
        """
        match self.backend:
            case RequestsCacheBackend.FILESYSTEM:
                assert self.filetype != RequestsCacheFileType.NONE, "File type 'none' is not compatible with filesystem backend."
            case _:
                assert self.filetype == RequestsCacheFileType.NONE, f"File type '{self.filetype}' is not compatible with {self.backend} backend."
        return self


    def root_dir_as_dict(self) -> dict[str, Any]:
        if script_info.is_unit_test():
            return {}

        return {
            'use_temp': self.root_dir == RequestsCacheRootDir.TEMP,
            'use_user_dir': self.root_dir == RequestsCacheRootDir.USER,
        }

    @property
    def cache_name_effective(self) -> str:
        # Unit tests cache to a hardcoded folder
        rel = os.path.join('test', 'cache') if script_info.is_unit_test() else self.cache_name

        if script_info.is_unit_test() or self.root_dir == RequestsCacheRootDir.SCRIPT_HOME:
            return os.path.join(script_info.get_script_home(), rel)
        else:
            return rel

    @property
    def backend_effective(self) -> RequestsCacheBackend:
        # Unit tests use the filesystem backend
        if script_info.is_unit_test():
            return RequestsCacheBackend.FILESYSTEM
        return self.backend

    @property
    def filetype_effective(self) -> RequestsCacheFileType:
        # Unit tests use JSON filetype
        if script_info.is_unit_test():
            return RequestsCacheFileType.JSON
        return self.filetype

    @property
    def expire_after_effective(self) -> PositiveInt | None:
        # Unit tests have no expiration
        if script_info.is_unit_test():
            return None
        return self.expire_after

    @property
    def ignored_parameters_effective(self) -> list[str]:
        # Unit tests ignore no parameters
        if script_info.is_unit_test():
            return []
        return self.ignored_parameters

    def as_kwargs(self) -> dict[str, Any]:
        result : dict[str, Any] = {
            'cache_name'        : self.cache_name_effective,
            'backend'           : self.backend_effective.value,
            'serializer'        : self.filetype_effective.value,
            'expire_after'      : self.expire_after_effective,
            'ignored_parameters': self.ignored_parameters_effective
        }

        result.update(self.root_dir_as_dict())

        return result