# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING
from typing import cast as typing_cast

from .class_decorator import CallguardClassDecorator
from .defines import CALLGUARD_ENABLED


if TYPE_CHECKING:
    from .types import CallguardClassOptions


# MARK: Callguard mixin
class CallguardMixin:
    if CALLGUARD_ENABLED:

        def __init_subclass__(cls) -> None:
            super().__init_subclass__()

            options = typing_cast("CallguardClassOptions | None", getattr(cls, "__callguard_class_options__", None))
            if options is None or not isinstance(options, dict):
                msg = "__callguard_class_options__ must be None or an instance of CallguardClassOptions"
                raise TypeError(msg)

            CallguardClassDecorator.guard(cls, **options)
