# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import BaseModel, ConfigDict


class ConfigBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)