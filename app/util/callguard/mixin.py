# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from .defines import CALLGUARD_ENABLED
from .class_decorator import CallguardClassDecorator


# MARK: Callguard mixin
class CallguardMixin:
    if CALLGUARD_ENABLED:
        def __init_subclass__(cls) -> None:
            super().__init_subclass__()
            CallguardClassDecorator.guard(cls)