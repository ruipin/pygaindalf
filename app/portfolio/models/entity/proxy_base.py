# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import functools
import inspect
import weakref

from abc import ABCMeta
from collections import abc
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, Unpack, override
from typing import cast as typing_cast

from ....util.callguard import callguard_class
from ....util.helpers import abc_info, generics, type_hints
from ....util.mixins import LoggableMixin
from . import Entity


if TYPE_CHECKING:
    from ...util.uid import Uid


class EntityProxyArgs(TypedDict, total=True):
    propagate: NotRequired[bool]
    propagate_untyped_collections: NotRequired[bool]
    propagate_getattr: NotRequired[bool]
    propagate_setattr: NotRequired[bool]
    propagate_callable_args: NotRequired[bool]
    propagate_callable_return: NotRequired[bool]


@callguard_class()
class EntityProxyImpl[T: Entity](type_hints.CachedTypeHintsMixin, LoggableMixin, metaclass=ABCMeta):
    # MARK: Construction
    def __new__(cls, entity_or_uid: T | Uid, *, create: bool = False, **options: Unpack[EntityProxyArgs]) -> EntityProxyImpl[T]:
        from .entity import Entity

        if create:
            instance = super().__new__(cls)
            instance._init(entity_or_uid, **options)
            return instance

        assert len(options) == 0, "Cannot pass options when create is False."

        entity_type = cls.get_entity_type()
        entity = Entity.narrow_to_entity(entity_or_uid)
        assert isinstance(entity, entity_type)

        return typing_cast("EntityProxyImpl[T]", entity.proxy)

    def __init__(self, entity_or_uid: T | Uid, *, _create: bool = False, **_options: Unpack[EntityProxyArgs]) -> None:
        super().__init__()
        assert Entity.narrow_to_uid(entity_or_uid) == self._uid

    def _init(self, entity_or_uid: T | Uid, **options: Unpack[EntityProxyArgs]) -> None:
        self._options = options

        from .entity import Entity

        uid = Entity.narrow_to_uid(entity_or_uid)
        self._uid = uid
        self._set_entity_or_uid(entity_or_uid)

    # NOTE: We swallow the init argument to avoid pyright issues with multiple inheritance and __init__ signatures.
    def __init_subclass__(cls, *, init: bool = False) -> None:
        super().__init_subclass__()

        entity_type = cls.get_entity_type(origin=True)
        for name, _ in inspect.getmembers_static(entity_type, predicate=inspect.isfunction):
            if (
                name.startswith("__")
                and name.endswith("__")
                and not hasattr(cls, name)
                and name
                not in ("__name__", "__qualname__", "__class__", "__init_subclass__", "__del__", "__getattribute__", "__setattr__", "__getattr__", "__dir__")
            ):
                setattr(cls, name, functools.partialmethod(cls.call_entity_method, name))

    # MARK: Options
    _options: EntityProxyArgs

    @property
    def _options_propagate(self) -> bool:
        return self._options.get("propagate", True)

    @property
    def _options_propagate_getattr(self) -> bool:
        return self._options.get("propagate_getattr", self._options_propagate)

    @property
    def _options_propagate_setattr(self) -> bool:
        return self._options.get("propagate_setattr", self._options_propagate)

    @property
    def _options_propagate_untyped_collections(self) -> bool:
        return self._options.get("propagate_untyped_collections", self._options_propagate)

    @property
    def _options_propagate_callable_args(self) -> bool:
        return self._options.get("propagate_callable_args", self._options_propagate)

    @property
    def _options_propagate_callable_return(self) -> bool:
        return self._options.get("propagate_callable_return", self._options_propagate)

    @property
    def _options_propagate_callables(self) -> bool:
        return self._options_propagate_callable_args or self._options_propagate_callable_return

    # MARK: Entity
    _uid: Uid
    _entity: weakref.ref[T]

    if TYPE_CHECKING:
        uid: Uid
    else:

        @property
        def uid(self) -> Uid:
            return self._uid

    get_entity_type = generics.GenericIntrospectionMethod[T]()

    def _set_entity_or_uid(self, entity_or_uid: T | Uid) -> T | None:
        entity_type = self.get_entity_type()
        entity = entity_type.narrow_to_entity_or_none(entity_or_uid)
        if entity is None:
            return None
        return self._set_entity(entity)

    def _set_entity(self, entity: T) -> T:
        if entity.uid != self.uid:
            msg = f"Cannot change entity proxy UID from {self.uid} to {entity.uid}."
            raise ValueError(msg)

        entity_type = self.get_entity_type()
        entity = entity_type.by_uid(self.uid)
        self._entity = weakref.ref(entity)
        return entity

    @property
    def entity_or_none(self) -> T | None:
        entity = self._entity()
        if entity is None:
            return self._set_entity_or_uid(self._uid)

        superseding = entity.superseding_or_none
        if superseding is None:
            return None

        if superseding is not entity:
            assert superseding.uid == self.uid
            entity = superseding
            self._entity = weakref.ref(superseding)

        return entity

    @property
    def entity(self) -> T:
        if (entity := self.entity_or_none) is None:
            msg = f"Could not find entity with UID {self.uid}. It may have been deleted."
            raise RuntimeError(msg)
        return entity

    if not TYPE_CHECKING:

        @property
        def proxy(self) -> EntityProxyImpl[T]:
            return self

    @property
    def deleted(self) -> bool:
        entity = self.entity_or_none
        return entity is None or entity.deleted

    @property
    def marked_for_deletion(self) -> bool:
        entity = self.entity_or_none
        return entity is None or entity.marked_for_deletion

    # MARK: Conversion - Entity to Proxy
    def _convert_abc_to_proxy(self, value: abc_info.ABCType, *, attr: str | None = None) -> abc_info.ABCType:
        kwargs = {}
        if attr is not None:
            kwargs["namespace"] = self.get_entity_type()
            kwargs["attr"] = attr

        info = abc_info.get_abc_info(value, **kwargs)
        if info.str_or_bytes:
            return value

        # If the collection is untyped and we don't want to propagate untyped collections, return as-is
        e = self.get_entity_type()
        e_origin = generics.get_origin(e, passthrough=True)

        if info.has_value:
            value_type = info.value_type
            hints = tuple(type_hints.iterate_type_hints(value_type, origin=True))
            assert hints
            if e_origin not in hints:
                return value
            allow_any = len(hints) > 1
        elif not self._options_propagate_untyped_collections:
            return value
        else:
            allow_any = True

        p = e.get_proxy_class()

        # Get the corresponding EntityProxyCollection class, if any, based on the primary ABC class
        klass = None
        from ...collections.entity_proxy import EntityProxyIterable, EntityProxyIterator

        if info.iterator:
            klass = EntityProxyIterator[e, p, abc.Iterator[p]]
        elif info.abc is abc.Iterable:
            klass = EntityProxyIterable[e, p, p]
        elif info.abc is abc.Mapping:
            from ...collections.entity_proxy import EntityProxyMapping

            klass = EntityProxyMapping[e, p]
        elif info.abc is abc.MutableMapping:
            from ...collections.entity_proxy import EntityProxyMutableMapping

            klass = EntityProxyMutableMapping[e, p]
        elif info.abc is abc.Set:
            from ...collections.entity_proxy import EntityProxySet

            klass = EntityProxySet[e, p]
        elif info.abc is abc.MutableSet:
            from ...collections.entity_proxy import EntityProxyMutableSet

            klass = EntityProxyMutableSet[e, p]
        elif info.abc is abc.Sequence:
            from ...collections.entity_proxy import EntityProxySequence

            klass = EntityProxySequence[e, p]
        elif info.abc is abc.MutableSequence:
            from ...collections.entity_proxy import EntityProxyMutableSequence

            klass = EntityProxyMutableSequence[e, p]

        if klass is None:
            msg = f"Cannot convert collection of type {type(value)} ({info.abc.__name__}) to proxy collection."
            raise TypeError(msg)

        return klass(instance=value, weakref=False, allow_any=allow_any)  # pyright: ignore[reportArgumentType] as we know this is allowed

    def _convert_to_proxy(self, value: Any, *, attr: str | None = None) -> Any:
        if isinstance(value, EntityProxyImpl):
            return value

        if isinstance(value, Entity):
            return value.proxy

        if isinstance(value, Callable):
            if not self._options_propagate_callables:
                return value
            elif attr is None:
                return functools.partial(self._call_method_with_propagation, value)
            else:
                return functools.partial(self.call_entity_method, attr)

        if isinstance(value, (abc.Collection, abc.Iterable)):
            return self._convert_abc_to_proxy(value, attr=attr)

        return value

    # MARK: Conversion - Proxy to Entity
    def _convert_to_entity(self, value: Any) -> Any:
        if isinstance(value, Entity):
            return value

        if isinstance(value, EntityProxyImpl):
            return value.entity

        if isinstance(value, abc.Collection):
            msg = "Conversion of collections from proxy to entity is not implemented."
            raise NotImplementedError(msg)

        return value

    # MARK: Fields
    @classmethod
    def _is_proxy_class_field(cls, field: str) -> bool:
        return hasattr(cls, field) or cls.__cached_type_hints__.get(field, None) is not None

    if not TYPE_CHECKING:

        @override
        def __getattribute__(self, name: str) -> Any:
            if name in (
                "__class__",
                "_is_proxy_class_field",
            ) or self._is_proxy_class_field(name):
                return super().__getattribute__(name)

            value = self.entity.__getattribute__(name)
            if self._options_propagate_getattr:
                value = self._convert_to_proxy(value, attr=name)
            return value

        @override
        def __setattr__(self, name: str, value: object) -> None:
            if self._is_proxy_class_field(name):
                return super().__setattr__(name, value)

            # Convert proxies back to entities before setting them on the entity
            if self._options_propagate_setattr:
                value = self._convert_to_entity(value)
            return self.entity.__setattr__(name, value)

    @override
    def __dir__(self) -> Iterable[str]:
        entity = self.entity_or_none
        if entity is None:
            return super().__dir__()

        values = set()
        for name in super().__dir__():
            values.add(name)
            yield name

        for name in dir(entity):
            if name not in values:
                yield name

    # MARK: Callables
    def _call_method_with_propagation[**P, R](self, method: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
        if self._options_propagate_callable_args:
            args = (self._convert_to_entity(arg) for arg in args)  # pyright: ignore[reportAssignmentType]
            kwargs = {k: self._convert_to_entity(v) for k, v in kwargs.items()}  # pyright: ignore[reportAssignmentType]

        result = method(*args, **kwargs)

        if self._options_propagate_callable_return:
            result = self._convert_to_proxy(result)

        return result

    def call_entity_method(self, name: str, *args, **kwargs) -> Any:
        method = getattr(self.entity, name)

        if self._options_propagate_callables:
            return self._call_method_with_propagation(method, *args, **kwargs)
        else:
            return method(*args, **kwargs)

    # MARK: Utilities
    @override
    def __str__(self) -> str:
        entity = self.entity_or_none
        if entity is None:
            return f"{type(self).__name__}({self.uid}, deleted=True)"

        return str(entity).replace(type(entity).__name__, type(self).__name__, 1)

    @override
    def __repr__(self) -> str:
        entity = self.entity_or_none
        if entity is None:
            return f"{type(self).__name__}({self.uid}, deleted=True)"

        return f"{type(self).__name__}({entity!r})"
