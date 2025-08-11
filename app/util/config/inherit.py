# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import rich.repr

from typing import Iterable, override, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass

from .context_stack import ContextStack


# MARK : Inherit Factory
class InheritFactory[T]:
    def __init__(self, default : T) -> None:
        self.default = default

    def search(self, name : str) -> dict[str, Any] | BaseModel | None:
        return ContextStack.find_inheritance(name)

    def __call__(self) -> T:
        return self.default

    @override
    def __repr__(self) -> str:
        return f'InheritFactory(default={self.default})'


def FieldInherit[T](default : T, *args, **kwargs) -> T:
    return Field(default_factory=InheritFactory(default), *args, **kwargs) # pyright: ignore [reportReturnType]


# MARK : Diffing
@dataclass
class AttributeSet:
    attrs : frozenset[str] | None = None

    def __init__(self, attrs : Iterable[str] | None = None):
        self.attrs = frozenset(attrs) if attrs is not None else None

    def __contains__(self, item: str) -> bool:
        if self.attrs is None:
            return False
        return item in self.attrs

    def __iter__(self) -> Iterable[str]:
        if self.attrs is None:
            return iter(())
        return iter(self.attrs)

    @override
    def __repr__(self) -> str:
        if self.attrs is None:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({", ".join(self.attrs)})'


class Inherit(AttributeSet):
    pass

class Default(AttributeSet):
    pass