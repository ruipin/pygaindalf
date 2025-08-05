# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import BaseModel, ConfigDict

from ...helpers.classproperty import ClassPropertyDescriptor


class ConfigBaseModel(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        ignored_types=(ClassPropertyDescriptor,)
    )