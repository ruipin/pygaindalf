# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


# Base provider
from ..component import component_entrypoint
from .provider import BaseProvider, BaseProviderConfig


__all__ = [
    "BaseProvider",
    "BaseProviderConfig",
    "component_entrypoint",
]
