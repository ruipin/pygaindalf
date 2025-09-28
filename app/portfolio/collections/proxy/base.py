# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import weakref as _weakref

from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from typing import override, cast as typing_cast, overload

from ....util.helpers import generics
from ....util.callguard import callguard_class


@callguard_class()
class ProxyBase[
    T_Item : object,
    T_Proxy : object,
    T_Instance : object
](
    metaclass=ABCMeta
):
    _instance  : _weakref.ref[object] | object
    _field     : str | None
    _allow_any : bool

    @overload
    def __init__(self, *, instance : T_Instance, weakref : bool = True, allow_any : bool = False): ...
    @overload
    def __init__(self, *, instance : object, field : str, weakref : bool = True, allow_any : bool = False): ...

    def __init__(self, *, instance : object, field : str | None = None, weakref : bool = True, allow_any : bool = False):
        self._instance = _weakref.ref(instance) if weakref else instance
        self._field = field
        self._allow_any = allow_any

    def _get_instance(self) -> object:
        if isinstance(self._instance, _weakref.ref):
            instance = self._instance()
            if instance is None:
                raise ValueError("Instance has been garbage collected")
        else:
            instance = self._instance
        return instance

    def _get_field(self) -> T_Instance:
        if self._field is None:
            return typing_cast(T_Instance, self._get_instance())
        else:
            return typing_cast(T_Instance, getattr(self._get_instance(), self._field))

    get_item_type       = generics.GenericIntrospectionMethod[T_Item    ]()
    get_proxy_type      = generics.GenericIntrospectionMethod[T_Proxy   ]()
    get_instance_type   = generics.GenericIntrospectionMethod[T_Instance]()

    def _convert_item_to_proxy(self, item: T_Item) -> T_Proxy:
        if item is None:
            raise ValueError(f"Value must not be None")

        item_type = self.get_item_type()
        item_origin_type = generics.get_origin(item_type, passthrough=True)
        if not isinstance(item, item_origin_type):
            if not self._allow_any:
                raise TypeError(f"Expected {item_type.__name__}, got {type(item).__name__}")
            else:
                return typing_cast(T_Proxy, item)

        proxy_type = self.get_proxy_type()
        proxy = self._do_convert_item_to_proxy(item, item_type, proxy_type)
        proxy_origin_type = generics.get_origin(proxy_type, passthrough=True)
        if not isinstance(proxy, proxy_origin_type):
            raise TypeError(f"{type(self).__name__}._do_convert_item_to_proxy() must return {proxy_type.__name__}, got {type(proxy).__name__}")

        return proxy

    @abstractmethod
    def _do_convert_item_to_proxy(cls, item : T_Item, item_type : type[T_Item], proxy_type : type[T_Proxy]) -> T_Proxy:
        raise NotImplementedError("Subclasses must implement _do_convert_item_to_proxy")

    def _convert_proxy_to_item(self, proxy: T_Proxy) -> T_Item:
        if proxy is None:
            raise ValueError(f"Value must not be None")

        proxy_type = self.get_proxy_type()
        proxy_origin_type = generics.get_origin(proxy_type, passthrough=True)
        if not isinstance(proxy, proxy_origin_type):
            if not self._allow_any:
                raise TypeError(f"Expected {proxy_type.__name__}, got {type(proxy).__name__}")
            else:
                return typing_cast(T_Item, proxy)

        item_type = self.get_item_type()
        item = self._do_convert_proxy_to_item(proxy, proxy_type, item_type)
        item_origin_type = generics.get_origin(item_type, passthrough=True)
        if not isinstance(item, item_origin_type):
            raise TypeError(f"{type(self).__name__}.do_convert_proxy_to_item() must return {item_type.__name__}, got {type(item).__name__}")

        return item

    @abstractmethod
    def _do_convert_proxy_to_item(self, proxy : T_Proxy, proxy_type : type[T_Proxy], item_type : type[T_Item]) -> T_Item:
        raise NotImplementedError("Subclasses must implement _do_convert_proxy_to_item")

    @override
    def __str__(self) -> str:
        return str(self._get_field())

    @override
    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self._get_field()!r}>"