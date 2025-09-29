# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import Field

from ...helpers.decimal import DecimalConfig
from .base_model import BaseConfigModel


# MARK: Default Configuration Model
class BaseDefaultConfig(BaseConfigModel):
    decimal: DecimalConfig = Field(default=DecimalConfig(), description="Default decimal configuration")
