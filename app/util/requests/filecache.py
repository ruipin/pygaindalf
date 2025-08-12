# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

from requests_cache import FileCache, BaseCache, FileDict
from requests_cache.backends.filesystem import get_cache_path # pyright: ignore[reportPrivateImportUsage]
from requests_cache.serializers.cattrs import _decode_content

class CustomFileCache(FileCache):
    """
    Custom FileCache that uses FileDict for storing responses and redirects.

    This class is a workaround for the fact that the default FileCache uses SQLite.
    While that is desirable for most use cases, it is not suitable for unit tests where we want to be able to check in human-readable files.
    """
    def __init__(self, *args, **kwargs):
        super(FileCache, self).__init__(*args, **kwargs)

        cache_name = kwargs.pop('cache_name')
        use_temp = kwargs.pop('use_temp', False)
        use_cache_dir = kwargs.pop('use_cache_dir', False)
        decode_content = kwargs.pop('decode_content', False)

        cache_dir = get_cache_path(cache_name, use_cache_dir=use_cache_dir, use_temp=use_temp)
        self.responses: FileDict = FileDict(
            cache_dir / 'responses', decode_content=decode_content, **kwargs
        )
        self.redirects: FileDict = FileDict( # pyright: ignore[reportIncompatibleVariableOverride] as this is the entire reason for this custom file cache implementation
            cache_dir / 'redirects', decode_content=decode_content, **kwargs
        )