# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import BaseModel, ConfigDict


class ForbidExtraBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid')