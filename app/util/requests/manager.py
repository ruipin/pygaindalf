# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from .config.requests import RequestsConfig
from .config.cache import RequestsCacheBackend

from .filecache import CustomFileCache
from .session import CustomSession

from ..helpers import script_info

import requests_cache
import pathlib
import urllib.parse
import os

from typing import Any


class RequestsManager:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RequestsManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        pass

    def initialize(self, config: RequestsConfig | dict[str, Any], install : bool = False):
        if not isinstance(config, RequestsConfig):
            config = RequestsConfig.model_validate(config)

        if self.initialized:
            raise RuntimeError(f"Must not initialise {type(self).__name__} twice")
        self.initialized = True

        self.config = config
        self.install()

    def _create_custom_file_cache(self, **kwargs) -> CustomFileCache:
        """
        Create a custom file cache instance based on the configuration.
        """
        filecache = getattr(self, 'filecache', None)
        if filecache is None:
            filecache = CustomFileCache(**kwargs)
            self.filecache = filecache
        return filecache

    def _get_config_kwargs(self) -> dict[str, Any]:
        kwargs = self.config.cache.as_kwargs()

        # We use a custom version of FileCache without any SQLite dependencies if the backend is FILESYSTEM
        # Since we will be checking in the cache, we want every file to be human-readable
        if kwargs['backend'] == RequestsCacheBackend.FILESYSTEM and script_info.is_unit_test():
            kwargs['backend'] = self._create_custom_file_cache(**kwargs)

        # If the backend is FILESYSTEM, we want to use human-readable cache keys
        if kwargs['backend'] == RequestsCacheBackend.FILESYSTEM:
            kwargs['key_fn'] = self.human_readable_key_fn

        return kwargs

    def install(self):
        """
        Install the requests_cache with the given configuration.
        """
        requests_cache.install_cache(session_factory=CustomSession, **self._get_config_kwargs())

    def session(self) -> Any:
        return CustomSession(**self._get_config_kwargs())


    # MARK: Cache methods
    def human_readable_key_fn(
        self,
        request: requests_cache.models.AnyRequest,
        ignored_parameters: requests_cache.cache_keys.ParamList = None,
        match_headers: requests_cache.cache_keys.ParamList | bool = False,
        serializer: Any = None,
        **request_kwargs,
    ) -> str:
        request = requests_cache.cache_keys.normalize_request(request, ignored_parameters)

        ### Parse the URL
        url = urllib.parse.urlparse(request.url)

        # Domain
        domain = str(url.netloc)
        assert domain, "Domain must not be empty in the request URL"

        # URL Path
        urlpath = pathlib.PurePosixPath(urllib.parse.unquote(url.path))

        path_parts = [
            domain,
            *urlpath.parts[1:]
        ]
        assert '/' not in path_parts, "Path parts must not contain a leading slash"

        ### Create a hash of the request using default implementation of create_key
        key_hash = requests_cache.cache_keys.create_key(request, ignored_parameters, match_headers, serializer, **request_kwargs)

        ### Finish by combining the path and hash
        relpath = pathlib.PurePath(*path_parts, key_hash)
        assert not relpath.is_absolute(), "Relative path must not be absolute"

        abspath = pathlib.PurePath(self.config.cache.cache_name_effective, relpath)
        os.makedirs(abspath.parent, exist_ok=True)

        return str(relpath)