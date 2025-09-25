# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import cast as typing_cast

from .defines import CALLGUARD_ENABLED
from .class_decorator import CallguardClassDecorator
from .types import CallguardClassOptions


# MARK: Callguard mixin
class CallguardMixin:
    if CALLGUARD_ENABLED:
        def __init_subclass__(cls) -> None:
            super().__init_subclass__()

            options = typing_cast(CallguardClassOptions | None, getattr(cls, '__callguard_class_options__', None))
            if options is None or not isinstance(options, dict):
                raise TypeError("__callguard_class_options__ must be None or an instance of CallguardClassOptions")

            CallguardClassDecorator.guard(cls, **options)