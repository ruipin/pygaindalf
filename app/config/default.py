# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import Field

from ..context import ContextConfig
from ..util.config.models.default import BaseDefaultConfig


# MARK: Main Config
class DefaultConfig(BaseDefaultConfig):
    context: ContextConfig = Field(default=ContextConfig(), description="Default context configuration")
