# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from app.util.callguard import callguard_class


@callguard_class(allow_same_module=False)
class TestDoubleUnderscore:
    def normal(self) -> str:
        return "normal ok"

    def normal2(self) -> str:
        return "normal2 ok"

    def _single_underscore(self) -> str:
        return "single underscore ok"

    def __double_underscore(self) -> str:
        return "double underscore ok"

    def access_double_underscore(self) -> str:
        # Internal access to double underscore method should be allowed
        return self.__double_underscore()