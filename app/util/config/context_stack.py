# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass
class ContextStack:
    type CurrentType = dict[str, Any] | BaseModel

    name: str | None = None
    parent: ContextStack | None = None
    current: CurrentType | None = None
    token: Token | None = None

    @classmethod
    def push(cls, current: CurrentType, name: str | None = None) -> ContextStack:
        """Push a new context onto the stack."""
        parent = CONFIG_CONTEXT.get(None)
        new_context = cls(name=name, parent=parent, current=current)
        new_context.token = CONFIG_CONTEXT.set(new_context)
        return new_context

    @classmethod
    def pop(cls, token: Token | None = None) -> None:
        """Pop the current context from the stack and return it.

        If the stack is empty, return None.
        """
        current = CONFIG_CONTEXT.get()
        if current is None:
            msg = "No context to pop from the stack"
            raise RuntimeError(msg)
        if current.token is None:
            msg = "Current context does not have a valid token"
            raise RuntimeError(msg)
        if token is not None and current.token != token:
            msg = "Provided token does not match the current context token"
            raise RuntimeError(msg)
        CONFIG_CONTEXT.reset(current.token)

    @classmethod
    def get(cls) -> ContextStack | None:
        """Get the current context from the stack.

        If the stack is empty, return None.
        """
        return CONFIG_CONTEXT.get(None)

    @classmethod
    def iterate(cls, skip: int = 0) -> Generator[ContextStack]:
        """Iterate over the current context and all parent contexts."""
        context = cls.get()
        while context is not None:
            if skip > 0:
                skip -= 1
            else:
                yield context
            context = context.parent

    @classmethod
    def find_inheritance(cls, name: str, skip: int = 0) -> dict[str, Any] | BaseModel | None:
        """Find a context by name in the stack."""
        scope = [name]

        for context in cls.iterate(skip=skip):
            # Search for the name in the current context
            _scope = [*scope, "default"]
            for i in range(len(_scope)):
                found = True
                obj: dict[str, Any] | BaseModel | None = context.current
                for s in _scope[i::-1]:
                    if isinstance(obj, dict):
                        if s not in obj:
                            found = False
                            break
                        obj = obj[s]
                    elif isinstance(obj, BaseModel):
                        if not hasattr(obj, s):
                            found = False
                            break
                        obj = getattr(obj, s)
                    else:
                        # If the object is neither a dict nor a BaseModel, we cannot find the scope.
                        found = False
                        break
                if found:
                    return obj

            if context.name is not None:
                scope.append(context.name)

        return None

    @classmethod
    def find_name(cls, name: str, skip: int = 0) -> bool:
        """Check if a context with the given name exists in the stack."""
        return any(context.name == name for context in cls.iterate(skip=skip))

    @classmethod
    @contextmanager
    def with_context(cls, current: CurrentType, name: str | None = None) -> Any:
        """Context manager to push a new context onto the stack."""
        context = cls.push(current, name=name)
        try:
            yield context
        finally:
            cls.pop(context.token)

    @classmethod
    @contextmanager
    def with_updated_name(cls, name: str) -> Any:
        context = cls.get()
        if context is None:
            msg = "No context to update the name"
            raise RuntimeError(msg)
        old_name = context.name
        context.name = name
        try:
            yield context
        finally:
            context.name = old_name


CONFIG_CONTEXT = ContextVar[ContextStack]("config_context")
