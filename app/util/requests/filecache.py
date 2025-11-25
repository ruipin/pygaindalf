# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, override

from requests_cache import FileCache, FileDict
from requests_cache.backends.filesystem import get_cache_path  # pyright: ignore[reportPrivateImportUsage]


class NoCookieFileDict(FileDict):
    """Custom FileDict that filters cookie values so they are not stored in the cache."""

    @override
    def serialize(self, value: Any) -> str | bytes | Any:
        """Serialize a value, if a serializer is available."""
        value.cookies.clear()
        value.headers.pop("Set-Cookie", None)
        value.headers.pop("CF-RAY", None)

        return super().serialize(value)


class CustomFileCache(FileCache):
    """Custom FileCache that uses FileDict for storing responses and redirects.

    This class is a workaround for the fact that the default FileCache uses SQLite.
    While that is desirable for most use cases, it is not suitable for unit tests where we want to be able to check in human-readable files.
    """

    def __init__(self, *args, **kwargs) -> None:
        super(FileCache, self).__init__(*args, **kwargs)

        cache_name = kwargs.pop("cache_name")
        use_temp = kwargs.pop("use_temp", False)
        use_cache_dir = kwargs.pop("use_cache_dir", False)
        decode_content = kwargs.pop("decode_content", False)

        cache_dir = get_cache_path(cache_name, use_cache_dir=use_cache_dir, use_temp=use_temp)
        self.responses: FileDict = NoCookieFileDict(cache_dir / "responses", decode_content=decode_content, **kwargs)
        self.redirects: FileDict = FileDict(  # pyright: ignore[reportIncompatibleVariableOverride] as this is the entire reason for this custom file cache implementation
            cache_dir / "redirects", decode_content=decode_content, **kwargs
        )
