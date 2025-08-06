# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import Field
from typing import override

from .base_model import BaseConfigModel
from ...helpers.decimal import DecimalConfig


# MARK: Default Configuration Model
class BaseDefaultConfig(BaseConfigModel):
    decimal: DecimalConfig = Field(default=DecimalConfig(), description="Default decimal configuration")