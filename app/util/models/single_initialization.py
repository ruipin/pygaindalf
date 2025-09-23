# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import BaseModel, PrivateAttr
from typing import Any, override, final

from ..callguard.pydantic_model import CallguardedModelMixin


class SingleInitializationModel(CallguardedModelMixin, BaseModel):
    __initialized : bool = PrivateAttr(default=False)

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance.__initialized = False
        return instance

    def __init__(self, *args, **kwargs):
        if self.initialized:
            raise RuntimeError(f"Model {self} is already initialized.")

        super().__init__(*args, **kwargs)
        self.__initialized = True

    @override
    def model_post_init(self, context : Any) -> None:
        super().model_post_init(context)

    @final
    @property
    def initialized(self) -> bool:
        return self.__initialized