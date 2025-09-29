# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import Any, Self, final, override

from pydantic import BaseModel, PrivateAttr

from ..callguard.pydantic_model import CallguardedModelMixin


class SingleInitializationModel(CallguardedModelMixin, BaseModel):
    __initialized: bool = PrivateAttr(default=False)

    def __new__(cls, *args, **kwargs) -> Self:
        instance = super().__new__(cls)
        instance.__initialized = False
        return instance

    def __init__(self, *args, **kwargs) -> None:
        if self.initialized:
            msg = f"Model {self} is already initialized."
            raise RuntimeError(msg)

        super().__init__(*args, **kwargs)
        self.__initialized = True

    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)

    @final
    @property
    def initialized(self) -> bool:
        return self.__initialized
