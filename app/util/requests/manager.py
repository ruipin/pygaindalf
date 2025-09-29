# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import pathlib
import urllib.parse

from typing import Any, Self

import requests_cache

from ..helpers import script_info
from .config.cache import RequestsCacheBackend
from .config.requests import RequestsConfig
from .filecache import CustomFileCache
from .session import CustomSession


class RequestsManager:
    _instance = None

    def __new__(cls, *args, **kwargs) -> Self:
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self) -> None:
        pass

    def initialize(self, config: RequestsConfig | dict[str, Any], *, install: bool = False) -> None:
        if not isinstance(config, RequestsConfig):
            config = RequestsConfig.model_validate(config)

        if self.initialized:
            msg = f"Must not initialise {type(self).__name__} twice"
            raise RuntimeError(msg)
        self.initialized = True

        self.config = config
        if install:
            self.install()

    def _create_custom_file_cache(self, **kwargs) -> CustomFileCache:
        """Create a custom file cache instance based on the configuration."""
        filecache = getattr(self, "filecache", None)
        if filecache is None:
            filecache = CustomFileCache(**kwargs)
            self.filecache = filecache
        return filecache

    def _get_config_kwargs(self) -> dict[str, Any]:
        kwargs = self.config.cache.as_kwargs()

        # We use a custom version of FileCache without any SQLite dependencies if the backend is FILESYSTEM
        # Since we will be checking in the cache, we want every file to be human-readable
        if kwargs["backend"] == RequestsCacheBackend.FILESYSTEM and script_info.is_unit_test():
            kwargs["backend"] = self._create_custom_file_cache(**kwargs)

        # If the backend is FILESYSTEM, we want to use human-readable cache keys
        if kwargs["backend"] == RequestsCacheBackend.FILESYSTEM:
            kwargs["key_fn"] = self.human_readable_key_fn

        return kwargs

    def install(self) -> None:
        """Install the requests_cache with the given configuration."""
        requests_cache.install_cache(session_factory=CustomSession, **self._get_config_kwargs())

    def session(self) -> Any:
        return CustomSession(**self._get_config_kwargs())

    # MARK: Cache methods
    def human_readable_key_fn(
        self,
        request: requests_cache.models.AnyRequest,
        ignored_parameters: requests_cache.cache_keys.ParamList = None,
        match_headers: requests_cache.cache_keys.ParamList | bool = False,  # noqa: FBT001, FBT002 as the method signature is defined by the requests library
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

        path_parts = [domain, *urlpath.parts[1:]]
        assert "/" not in path_parts, "Path parts must not contain a leading slash"

        ### Create a hash of the request using default implementation of create_key
        key_hash = requests_cache.cache_keys.create_key(request, ignored_parameters, match_headers, serializer, **request_kwargs)

        ### Finish by combining the path and hash
        relpath = pathlib.PurePath(*path_parts, key_hash)
        assert not relpath.is_absolute(), "Relative path must not be absolute"

        abspath = pathlib.PurePath(self.config.cache.cache_name_effective, relpath)
        pathlib.Path(abspath.parent).mkdir(exist_ok=True, parents=True)

        return str(relpath)
