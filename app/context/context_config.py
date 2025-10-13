# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta

from ..util.config import BaseConfigModel
from ..util.config.inherit import FieldInherit
from ..util.helpers.decimal import DecimalConfig


class ContextConfig(BaseConfigModel, metaclass=ABCMeta):
    decimal: DecimalConfig = FieldInherit(default_factory=DecimalConfig, description="Decimal configuration for context")

    providers_remap: dict[str, str] = FieldInherit(default_factory=dict, description="Remap of provider keys")
