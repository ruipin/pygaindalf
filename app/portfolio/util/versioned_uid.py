# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Protocol, runtime_checkable

from .uid import UidProtocol


@runtime_checkable
class VersionedUid(UidProtocol, Protocol):
    @property
    def version(self) -> int: ...

    def is_newer_version_than(self, other: VersionedUid) -> bool: ...
