# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import rich.repr

from typing import override, Any
from pydantic import BaseModel


# MARK : Default Factory
class DefaultFactory[T]:
    def __init__(self, scope : str | tuple[str, ...], model : type[T]):
        if isinstance(scope, str):
            self.scope : tuple[str, ...] = tuple(scope.split('.'))
        else:
            self.scope = scope

        self.model = model
        self.default = self.model()

    def get_scope(self, root_model : BaseModel) -> T:
        obj = root_model
        scope = self.scope
        for part in scope:
            obj = getattr(obj, part, None)
            if obj is None:
                raise ValueError(f"Default context does not contain scope '{'.'.join(scope)}'")

        if not isinstance(obj, self.model):
            raise TypeError(f"Expected object of type {self.model.__name__} at scope '{'.'.join(scope)}', got {type(obj).__name__}")

        return obj

    def __call__(self) -> T:
        return self.default

    @override
    def __repr__(self) -> str:
        return f'DefaultFactory(scope={self.scope}, model={self.model.__name__})'


class ClassRenamer:
    def __init__(self, name : str, cls: type):
        self.name = name
        self.cls = cls

    @override
    def __getattribute__(self, item: str) -> Any:
        if item == '__name__':
            return self.name
        else:
            return super().__getattribute__(item)

    @override
    def __repr__(self) -> str:
        return f'ClassRenamer({self.name}, {self.cls.__name__})'


# MARK : Diffing
class Default:
    def __init__(self, attrs : list[str]):
        self.attrs = attrs

    @override
    def __repr__(self) -> str:
        return f'Default({", ".join(self.attrs)})'


class DefaultDiff[T : BaseModel]():
    def __init__(self, value : T, default : T):
        self.value = value
        self.default = default

    @override
    def __getattribute__(self, item: str) -> Any:
        if item == '__class__':
            return ClassRenamer(self.value.__class__.__name__, super().__getattribute__('__class__'))
        else:
            return super().__getattribute__(item)

    def __rich_repr__(self) -> rich.repr.Result:
        l = []
        for attr, info in self.value.__class__.model_fields.items():
            value = getattr(self.value, attr, None)
            default = getattr(self.default, attr, None)
            if value == default:
                l.append(attr)
                continue
            yield attr, value
        yield Default(l)