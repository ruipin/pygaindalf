# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Utilities for generic type introspection and resolution.

This module wraps the Python typing machinery (and some Pydantic internals)
to make it easy to:

* inspect the parameters declared on a generic class or alias,
* examine how those parameters are specialised on subclasses and aliases,
* follow argument bindings through entire inheritance hierarchies, and
* expose reusable descriptors that resolve type arguments on demand.

Most library methods raise :class:`GenericsError` when the caller provides
inputs that make resolution impossible (for example, asking for a parameter
that was never declared, or querying a non-generic class).

Repeated lookups are cached so the helpers remain inexpensive when used
repeatedly.


Examples
========

*1. Inspect concrete types of generic type parameters*

    Parameters declared by a generic class or alias can be inspected using
    :func:`get_parameter_infos`::

        >>> class Parent[T]:
        ...     pass
        >>> class Child(Parent[list[int]]):
        ...     pass
        >>> from app.util.helpers import generics
        >>> generics.get_concrete_parent_argument(Child, Parent, "T")
        list[int]

*2. Class descriptors for generic type parameter introspection*

    Classes can expose reusable introspection class methods by using
    :class:`GenericIntrospectionMethod`::

        >>> from app.util.helpers import generics
        >>> class Repository[T]:
        ...     item_type        = generics.GenericIntrospectionMethod[T]()
        ...     item_type_origin = generics.GenericIntrospectionMethod[T](origin=True)
        >>> class StrRepository(Repository[str]):
        ...     pass
        >>> StrRepository.item_type()
        <class 'str'>
        >>> class IntListRepository(Repository[list[int]]):
        ...     pass
        >>> IntListRepository.item_type()
        list[int]
        >>> IntListRepository.item_type_origin()
        <class 'list'>

    Instances can also invoke the descriptor directly:

        >>> IntListRepository().item_type()
        list[int]

    The descriptor enforces type argument bounds if present:

        >>> class Animal: ...
        >>> class Dog(Animal): ...
        >>> class AnimalRepository[T : Animal](Repository[T]):
        ...     animal_type = generics.GenericIntrospectionMethod[T]()
        >>> AnimalRepository.animal_type()
        <class 'app.util.helpers.generics.Animal'>
        >>> class IntRepository(AnimalRepository[int]): ...
        >>> IntRepository.animal_type()     # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        GenericsError: IntRepository.T type argument <class 'int'> is not a subclass of <class '__main__.Animal'>

    This can be turned off by passing `bound=False` to the descriptor
    instantiation or the method call:

        >>> IntRepository.animal_type(bound=False)
        <class 'int'>

    You can also pass a ``source`` alias to cover cases where ``cls`` has lost
    its generic specialisation:

        >>> alias = Repository[int]
        >>> Repository.item_type(source=alias)
        <class 'int'>

See ``test/util/helpers/test_generic_introspection_method.py`` for more involved
scenarios.
"""

import typing
import types
import annotationlib
import functools
import warnings

from frozendict import frozendict
from functools import lru_cache

from .instance_lru_cache import instance_lru_cache

# Maximum number of cached entries used by the memoization helpers below.
LRU_CACHE_MAXSIZE = 128

# MARK: Definitions
# Runtime-compatible alias for representing generic annotations on Python < 3.12.
type GenericAlias = types.GenericAlias | typing._GenericAlias # pyright: ignore[reportAttributeAccessIssue] as typing._GenericAlias does exist, but is undocumented

# Identifiers accepted when referring to a generic parameter definition.
type ParamType = str | typing.TypeVar | ParameterInfo
# Values that may appear as a bound argument for a generic parameter.
type ArgType = type | typing.TypeVar | GenericAlias
# Resolved bounds allowed to constrain a ``TypeVar`` argument.
type BoundType = ArgType | typing.ForwardRef | None

class GenericsError(TypeError):
    """Signals incorrect generic usage outside the helpers' control.

    This error is specifically raised when callers provide inputs that make
    generic resolution impossible (for example, referencing an unknown type
    parameter or asking for generic state on a non-generic class).

    Internal errors within this module surface via other exception types.
    """


class ParameterInfo(typing.NamedTuple):
    """Metadata describing a generic type parameter for a class or alias."""
    position : int
    value    : typing.TypeVar
    origin   : type | GenericAlias

    @property
    def name(self) -> str:
        """Return the parameter name derived from the underlying ``TypeVar``."""
        return self.value.__name__

    @property
    def bound(self) -> BoundType:
        """Return the evaluated bound of the underlying ``TypeVar`` if present."""
        if (evaluate_bound := getattr(self.value, 'evaluate_bound', None)) is None:
            return None
        return annotationlib.call_evaluate_function(evaluate_bound, format=annotationlib.Format.FORWARDREF)

    @classmethod
    def narrow(cls, target_cls : type | GenericAlias, param : ParameterInfo | str | typing.TypeVar) -> ParameterInfo:
        """Resolve arbitrary parameter identifiers into a concrete ``ParameterInfo``.

        Raises:
            GenericsError: If *param* is not declared on *target_cls*.
        """
        if isinstance(param, (str, typing.TypeVar)):
            return get_parameter_info(target_cls, param)
        elif isinstance(param, ParameterInfo):
            return param
        else:
            raise TypeError(f"param must be a str, ParameterInfo or TypeVar, got {type(param).__name__}")

    def get_argument_info(self) -> ArgumentInfo:
        """Return the currently bound argument metadata for this parameter."""
        return get_argument_info(self.origin, self)

    def get_argument(self) -> ArgType:
        """Return the raw argument bound to this parameter for the originating class."""
        return get_argument(self.origin, self)

    @typing.override
    def __str__(self) -> str:
        """Return a human-friendly parameter identifier."""
        return self.name


class ArgumentInfo(typing.NamedTuple):
    """Metadata describing the argument bound to a ``ParameterInfo``."""

    parameter : ParameterInfo
    value     : ArgType

    @property
    def name(self) -> str:
        """Return a display-friendly name for the currently bound value."""
        val = self.value_or_bound
        if val is None:
            return 'None'
        elif isinstance(val, typing.ForwardRef):
            return val.__forward_arg__
        else:
            return val.__name__

    @property
    def is_concrete(self) -> bool:
        """Return ``True`` if the argument is a concrete type rather than a ``TypeVar``."""
        return not isinstance(self.value, typing.TypeVar)

    @property
    def bound(self) -> BoundType:
        """Return the evaluated bound for the underlying ``TypeVar`` argument."""
        if not isinstance(self.value, typing.TypeVar):
            raise TypeError(f"Only TypeVar arguments have bounds, got {type(self.value).__name__}")
        if (evaluate_bound := getattr(self.value, 'evaluate_bound', None)) is None:
            return None
        return annotationlib.call_evaluate_function(evaluate_bound, format=annotationlib.Format.FORWARDREF)

    @property
    def value_or_bound(self) -> ArgType | BoundType:
        """Return the concrete value if available, otherwise fall back to the bound."""
        if self.is_concrete:
            return self.value
        else:
            bound = self.bound
            return self.value if bound is None else bound

    @typing.override
    def __str__(self) -> str:
        """Return a human-friendly representation of the argument."""
        return self.name


# MARK: Pydantic helpers
try:
    import pydantic
except:
    pydantic = None

def is_pydantic_model(cls : type | GenericAlias) -> bool:
    """Return whether *cls* resolves to a Pydantic ``BaseModel`` subclass."""
    origin = get_origin(cls, passthrough=True)
    return pydantic is not None and issubclass(origin, pydantic.BaseModel)


# MARK: get_bases
def get_original_bases(cls : type | GenericAlias) -> tuple[typing.Any, ...]:
    """Return the tuple of original bases for *cls*, resolving aliases.

    Raises:
        GenericsError: If *cls* does not describe a generic class.
    """
    if not isinstance(cls, type):
        _cls = typing.get_origin(cls)
        if _cls is None:
            raise GenericsError(f"{cls} is not a generic class")
        cls = _cls

    return types.get_original_bases(cls)


# MARK: get_origin
def get_origin_or_none(cls : type | GenericAlias) -> type | None:
    """Return the typing origin for *cls* or ``None`` when not generic."""
    return typing.get_origin(cls)

def get_origin(cls : type | GenericAlias, *, passthrough : bool = False) -> type:
    """Return the typing origin for *cls* or ``cls`` itself when passthrough is ``True``.

    Raises:
        GenericsError: If *cls* has no origin and ``passthrough`` is ``False``.
    """
    if (origin := get_origin_or_none(cls)) is not None:
        return origin
    elif not passthrough:
        raise GenericsError(f"{cls.__name__} is not a generic class")
    else:
        return typing.cast(type, cls)


# MARK: get_generic_base
def get_generic_base_or_none(cls : type | GenericAlias) -> type | None:
    """Return the generic base class for *cls* if one exists."""
    if is_pydantic_model(cls):
        metadata = cls.__pydantic_generic_metadata__
        if metadata['origin']:
            cls = metadata['origin']
            metadata = cls.__pydantic_generic_metadata__
        if not metadata['parameters']:
            return None
        return typing.cast(type, cls)

    bases = get_original_bases(cls)
    for base in bases:
        if get_origin_or_none(base) is typing.Generic:
            return base

    return None

def get_generic_base(cls : type | GenericAlias) -> type:
    """Return the generic base class for *cls*.

    Raises:
        GenericsError: If *cls* is not a generic class.
    """
    if (base := get_generic_base_or_none(cls)) is None:
        raise GenericsError(f"{cls.__name__} is not a generic class")
    return base


# MARK: iter/get_parameter_infos
def _get_parameters(cls : type) -> typing.Sequence[typing.TypeVar]:
    """Return the ``TypeVar`` sequence declared by the generic base class."""
    if is_pydantic_model(cls):
        return cls.__pydantic_generic_metadata__['parameters']
    else:
        return typing.get_args(cls)

def iter_parameter_infos(cls : type | GenericAlias, *, fail : bool = True) -> typing.Generator[ParameterInfo]:
    """Yield ``ParameterInfo`` entries for each generic parameter of *cls*.

    Raises:
        GenericsError: If *cls* is not generic and ``fail`` is ``True`` or if
            any declared parameter is not a ``TypeVar``.
    """
    generic = get_generic_base_or_none(cls)
    if generic is None:
        if fail:
            raise GenericsError(f"{cls.__name__} is not a generic class")
        return

    params = _get_parameters(generic)
    for pos, param in enumerate(params):
        if not isinstance(param, typing.TypeVar):
            raise GenericsError(f"Expected all generic arguments to be TypeVars, got {param} at position {pos} in {cls.__name__}")

        yield ParameterInfo(
            position = pos  ,
            value    = param,
            origin   = cls  ,
        )

@lru_cache(maxsize=LRU_CACHE_MAXSIZE)
def get_parameter_infos(cls : type | GenericAlias, *, fail : bool = True) -> typing.Mapping[str, ParameterInfo]:
    """Return a mapping of parameter names to ``ParameterInfo`` for *cls*.

    Results are cached via :func:`functools.lru_cache` with
    ``LRU_CACHE_MAXSIZE`` to avoid recomputing metadata for repeated lookups.

    Raises:
        GenericsError: Propagated from :func:`iter_parameter_infos` when *cls*
            is not generic or has invalid parameter declarations.
    """
    result = {info.name: info for info in iter_parameter_infos(cls, fail=fail)}
    return frozendict(result)


# MARK: get_parameter_info
def get_parameter_info_or_none(cls : type | GenericAlias, name_or_typevar : str | typing.TypeVar) -> ParameterInfo | None:
    """Return a specific ``ParameterInfo`` by name or ``TypeVar`` if present."""
    name = name_or_typevar if isinstance(name_or_typevar, str) else name_or_typevar.__name__

    for param in iter_parameter_infos(cls):
        if param.name == name:
            return param

    return None

def get_parameter_info(cls : type | GenericAlias, name_or_typevar : str | typing.TypeVar) -> ParameterInfo:
    """Resolve *name_or_typevar* to a ``ParameterInfo``.

    Raises:
        GenericsError: If the requested parameter is not defined on *cls*.
    """
    if (param := get_parameter_info_or_none(cls, name_or_typevar)) is None:
        raise GenericsError(f"Could not find generic parameter {name_or_typevar} in {cls.__name__}")
    return param


# MARK: has_parameter
def has_parameter(cls : type | GenericAlias, param : str | typing.TypeVar) -> bool:
    """Return ``True`` if *cls* defines a generic parameter matching *param*."""
    info = get_parameter_info_or_none(cls, param)
    return info is not None


# MARK: get_argument_info
def _sanity_check_arg_bound(*, param : ParameterInfo, arg : ArgType) -> None:
    """Ensure ``arg`` respects the bound defined on *param*."""
    arg_origin = get_origin(arg, passthrough=True)
    if not isinstance(arg_origin, type):
        return

    bound = param.bound
    if bound is None:
        return
    bound_origin = get_origin(bound, passthrough=True)
    if not isinstance(bound_origin, type):
        return

    if not issubclass(arg_origin, bound_origin):
        bound_str = (
            bound.__name__ if isinstance(bound, type)
            else bound.__forward_arg__ if isinstance(bound, typing.ForwardRef)
            else str(bound)
        )
        raise TypeError(f"{param.origin.__name__}.{param.name} type argument <{arg.__name__}> is not a subclass of its bound <{bound_str}>")

def _get_arguments(cls : type | GenericAlias) -> typing.Sequence[ArgType]:
    """Return the argument sequence currently bound to *cls*."""
    if is_pydantic_model(cls):
        return cls.__pydantic_generic_metadata__['args']
    else:
        return typing.get_args(cls)

def get_argument_info_or_none(cls : GenericAlias, param : ParamType, *, check_bounds : bool = True, args : typing.Sequence[ArgType] | None = None) -> ArgumentInfo | None:
    """Return the ``ArgumentInfo`` for *param* if the binding exists on *cls*.

    Raises:
        GenericsError: If *param* cannot be resolved on *cls*.
    """
    param = ParameterInfo.narrow(cls, param)

    # Get the actual type argument at that index
    if args is None:
        args = _get_arguments(cls)

    arg = None
    if len(args) > param.position:
        arg = args[param.position]
        if check_bounds:
            _sanity_check_arg_bound(param=param, arg=arg)

    if arg is None:
        return None
        arg = param.value

    return ArgumentInfo(
        parameter = param,
        value     = arg  ,
    )

def get_argument_info(cls : GenericAlias, param : ParamType, *, check_bounds : bool = True, args : typing.Sequence[ArgType] | None = None) -> ArgumentInfo:
    """Return the ``ArgumentInfo`` for *param* or fall back to the raw ``TypeVar``.

    Raises:
        GenericsError: If *param* cannot be resolved on *cls*.
    """
    param = ParameterInfo.narrow(cls, param)

    if (arg := get_argument_info_or_none(cls, param, check_bounds=check_bounds, args=args)) is None:
        return ArgumentInfo(
            parameter = param,
            value     = param.value, # Fallback to the TypeVar if we can't find a specialisation
        )
    return arg



# MARK: iter/get_argument_infos
def iter_argument_infos(cls : GenericAlias, *, fail : bool = True, args : typing.Sequence[ArgType] | None = None) -> typing.Generator[ArgumentInfo]:
    """Yield ``ArgumentInfo`` values for each generic parameter on *cls*.

    Raises:
        GenericsError: If *cls* is not generic or any parameter cannot be
            resolved.
    """
    for info in iter_parameter_infos(cls, fail=fail):
        yield get_argument_info(cls, info, args=args)

@lru_cache(maxsize=LRU_CACHE_MAXSIZE)
def get_argument_infos(cls : GenericAlias, *, fail : bool = True, args : typing.Sequence[ArgType] | None = None) -> typing.Mapping[str, ArgumentInfo]:
    """Return a cached mapping of parameter names to ``ArgumentInfo`` for *cls*.

    Results are cached via :func:`functools.lru_cache` with
    ``LRU_CACHE_MAXSIZE`` so repeated argument inspections stay inexpensive.

    Raises:
        GenericsError: If *cls* is not generic or any parameter cannot be
            resolved.
    """
    result = {arg.parameter.name: arg for arg in iter_argument_infos(cls, fail=fail, args=args)}
    return frozendict(result)


# MARK: get_argument
def get_argument(cls : GenericAlias, param : ParamType) -> ArgType:
    """Return the raw type argument bound to *param* for *cls*.

    Raises:
        GenericsError: If *param* cannot be resolved on *cls*.
    """
    return get_argument_info(cls, param).value

def get_concrete_argument(cls : GenericAlias, param : ParamType) -> type:
    """Return the concrete origin type bound to *param* for *cls*.

    Raises:
        GenericsError: If *param* cannot be resolved to a concrete,
            generic-aware type.
    """
    param = ParameterInfo.narrow(cls, param)

    arg = get_argument(cls, param)
    if isinstance(arg, typing.TypeVar):
        raise GenericsError(f"Could not resolve {cls.__name__}.{param.name} type argument to a concrete type")

    origin = get_origin_or_none(arg)
    if origin is None:
        raise GenericsError(f"{cls.__name__}.{param.name} type argument is not a generic type, got <{arg.__name__}>")

    return origin



# MARK: get_bases_between
def get_bases_between(cls : type | GenericAlias, parent : type, result : list[type | GenericAlias] | None = None) -> list[type | GenericAlias]:
    """Return the inheritance chain between *cls* and *parent*, inclusive.

    Raises:
        GenericsError: If *cls* is not a subclass of *parent* or the chain
            includes non-generic components that cannot be inspected.
    """
    if result is None:
        result = []

    result.append(cls)
    if cls is parent:
        return result

    cls_origin = get_origin(cls, passthrough=True)
    if cls_origin is parent:
        return result

    bases = get_original_bases(cls_origin)
    for base in bases:
        origin = get_origin(base, passthrough=True)

        if origin is parent:
            result.append(base)
            return result

        if issubclass(origin, parent):
            return get_bases_between(base, parent, result)

    raise GenericsError(f"{cls.__name__} is not a subclass of {parent.__name__}")


# MARK: get_parent_argument_infos
def iter_parent_argument_infos(cls : type | GenericAlias, parent : type, param : ParamType) -> typing.Generator[ArgumentInfo]:
    """Yield argument bindings for *param* across the inheritance chain to *parent*.

    Raises:
        GenericsError: If the inheritance chain or requested parameter cannot
            be resolved.
    """
    param = ParameterInfo.narrow(parent, param)

    bases = get_bases_between(cls, parent)
    if not bases:
        raise GenericsError(f"{cls.__name__} is not a subclass of {parent.__name__}")

    current = None
    for base in reversed(bases):
        # NOTE: We use check_bounds=False here as we will check the final concrete type at the end
        #       and we want to do a depth-first traversal of the bounds i.e. the parent should check its bounds first, then the first child, then the second, etc.
        if current is None:
            current = get_argument_info(base, param, check_bounds=False)
        else:
            typevar = current.value
            if not isinstance(typevar, typing.TypeVar):
                raise GenericsError(f"Expected {base.__name__}.{param.name} to be a TypeVar, got {typevar}")

            #print(f"Looking for {typevar} in {base.__name__}")
            next_arg = get_argument_info_or_none(base, typevar, check_bounds=False)
            if next_arg is None:
                # Pydantic models sometimes 'skip' bases, i.e. some of the bases in the chain have the parameter but no specialisation
                if is_pydantic_model(base) and has_parameter(base, typevar):
                    continue
                # Otherwise we assume that the last parameter we saw is the last one that was specialised, and stop here
                else:
                    break
            current = next_arg

        yield current
        if current.is_concrete:
            return

@lru_cache(maxsize=LRU_CACHE_MAXSIZE)
def get_parent_argument_infos(cls : type | GenericAlias, parent : type, param : ParamType) -> typing.Sequence[ArgumentInfo]:
    """Return the cached sequence of argument bindings from *cls* to *parent*.

    Results are cached via :func:`functools.lru_cache` with
    ``LRU_CACHE_MAXSIZE`` so the inheritance chain is walked only once per
    parameter combination.

    Raises:
        GenericsError: Propagated when the inheritance chain or parameter
            cannot be resolved.
    """
    return tuple(iter_parent_argument_infos(cls, parent, param))


# MARK: get_parent_argument_info
def get_parent_argument_info_or_none(cls : type | GenericAlias, parent : type, param : ParamType, *, check_bounds : bool = True) -> ArgumentInfo | None:
    """Return the final ``ArgumentInfo`` for *param* inherited from *parent* if any.

    Raises:
        GenericsError: If the inheritance chain or requested parameter cannot
            be resolved.
    """
    if check_bounds:
        args = get_parent_argument_infos(cls, parent, param)
        result =args[-1] if args else None
    else:
        args = None
        result = None
        for result in iter_parent_argument_infos(cls, parent, param):
            pass

    # Sanity check the concrete specialisation against any bounds
    if check_bounds and result is not None and result.is_concrete:
        assert args is not None, "args should be set if check_bounds is True and result is not None"
        for arg in args:
            _sanity_check_arg_bound(param=arg.parameter, arg=result.value)

    return result

def get_parent_argument_info(cls : type | GenericAlias, parent : type, param : ParamType, *, check_bounds : bool = True) -> ArgumentInfo:
    """Return the resolved ``ArgumentInfo`` for *param* from *parent*.

    Raises:
        GenericsError: If the inheritance chain does not specialise *param*.
    """
    if (arg := get_parent_argument_info_or_none(cls, parent, param, check_bounds=check_bounds)) is None:
        raise GenericsError(f"Could not resolve {cls.__name__}.{param} type argument to a concrete type")
    return arg


# MARK: get_parent_argument
class GetParentArgumentKwargs(typing.TypedDict, total=True):
    """Typed keyword arguments accepted by ``get_parent_argument``."""
    bound : typing.NotRequired[type | bool]

def get_parent_argument[T : type](cls : T, parent : T, param : ParamType, **kwargs : typing.Unpack[GetParentArgumentKwargs]) -> ArgType:
    """Return the value or bound resolved for *param* on *parent* within *cls*.

    Raises:
        GenericsError: If *param* cannot be resolved or violates the optional
            ``bound`` constraint.
    """
    bound = kwargs.get('bound', True)

    arg = get_parent_argument_info(
        cls,
        parent,
        param,
        check_bounds=True if bound is True else False
    )
    result = arg.value_or_bound

    if not isinstance(bound, bool):
        result_origin = get_origin(result, passthrough=True)
        if not issubclass(result_origin, bound):
            raise GenericsError(f"{cls.__name__}.{param} type argument {result} is not a subclass of {bound}")

    return result


class GetConcreteParentArgumentKwargs(GetParentArgumentKwargs, total=True):
    """Typed keyword arguments accepted by ``get_concrete_parent_argument``."""
    origin : typing.NotRequired[bool]

def get_concrete_parent_argument[T : type](cls : T, parent : T, param : ParamType, **kwargs : typing.Unpack[GetConcreteParentArgumentKwargs]) -> ArgType:
    """Return the concrete argument resolved for *param* from *parent* within *cls*.

    Raises:
        GenericsError: If *param* cannot be resolved to a concrete type.
    """
    arg = get_parent_argument(cls, parent, param, **kwargs)

    if arg is None or isinstance(arg, typing.TypeVar):
        raise GenericsError(f"Could not resolve {cls.__name__}.{param} type argument to a concrete type, got <{arg}>")
    if isinstance(arg, typing.ForwardRef):
        raise NotImplementedError("ForwardRef resolution not yet implemented")

    if kwargs.get('origin', False):
        return get_origin(arg, passthrough=True)

    return arg

def get_concrete_parent_argument_origin[T : type](cls : T, parent : T, param : ParamType, **kwargs : typing.Unpack[GetConcreteParentArgumentKwargs]) -> type:
    """Return the origin type for the concrete argument resolved from *parent*.

    Raises:
        GenericsError: If *param* cannot be resolved to a concrete type.
    """
    if kwargs.get('origin', None) is False:
        raise ValueError("get_concrete_parent_argument_origin always sets origin=True, do not pass it in kwargs")
    kwargs['origin'] = True
    return typing.cast(type, get_concrete_parent_argument(cls, parent, param, **kwargs))


# MARK: introspection method descriptor
class GenericIntrospectionMethod[R : object](classmethod[typing.Any, ..., type[R]]):
    """Descriptor that resolves generic parent arguments on demand."""

    __callguarded__ : typing.ClassVar[bool] = True # Prevent callguard from acting on this descriptor
    _parent : type | None = None
    _param : typing.TypeVar

    @typing.override
    def __class_getitem__(cls, arg : typing.TypeVar) -> GenericAlias:
        """Allow ``GenericIntrospectionMethod[T]`` style usage with a ``TypeVar``."""
        if not isinstance(arg, typing.TypeVar):
            raise TypeError(f"GenericIntrospectionMethod expects a TypeVar parameter, got {type(arg).__name__}")
        return functools.partial(GenericIntrospectionMethod, arg)

    @property
    def _bound(self) -> type | None:
        """Return the concrete bound declared on the stored ``TypeVar`` if any."""
        if (evaluate_bound := getattr(self._param, 'evaluate_bound', None)) is None:
            return None
        bound = annotationlib.call_evaluate_function(evaluate_bound, format=annotationlib.Format.FORWARDREF)
        if isinstance(bound, typing.ForwardRef):
            warnings.warn("ForwardRef resolution not yet implemented, no bounds will be enforced", stacklevel=2)
            return None
        bound = get_origin(bound, passthrough=True)
        if not isinstance(bound, type):
            warnings.warn(f"GenericIntrospectionMethod only currently supports concrete type bounds, got {bound}, no bounds will be enforced", stacklevel=2)
            return None
        return bound

    def __init__(self, param : typing.TypeVar | None = None, **kwargs : typing.Unpack[GetConcreteParentArgumentKwargs]) -> None:
        """Initialise the descriptor and capture default keyword arguments."""
        if param is None:
            raise TypeError("GenericIntrospectionMethod must be subscripted with a TypeVar parameter, e.g. GenericIntrospectionMethod[T](), or explicitly passed a TypeVar parameter, e.g. GenericIntrospectionMethod(T)")
        self._param  = param
        self._kwargs = kwargs
        super().__init__(self.introspect)

    def __set_name__(self, owner : type, name : str):
        """Attach the descriptor to *owner* and record metadata for introspection."""
        self._parent = owner
        self.__name__ = name
        self.__qualname__ = f"{owner.__qualname__}.{name}"

    def _update_kwargs(self, kwargs : GetConcreteParentArgumentKwargs) -> GetConcreteParentArgumentKwargs:
        """Merge instance defaults and enforce ``TypeVar`` bounds on *kwargs*."""
        for k, v in self._kwargs.items():
            if k not in kwargs:
                kwargs[k] = v

        bound = self._bound
        if bound is not None and kwargs.get('bound', None) is None:
            kwargs['bound'] = bound

        return kwargs

    @instance_lru_cache
    def introspect[T : type](self, cls : type[T], source : type[T] | None = None, **kwargs : typing.Unpack[GetConcreteParentArgumentKwargs]) -> type[R]:
        """Resolve and cache the concrete parent argument defined by the descriptor.

        The descriptor caches the result per owning class via
        :func:`instance_lru_cache` so repeated introspections remain constant
        time.

        Raises:
            GenericsError: If the underlying parent argument cannot be
                resolved to a concrete type.
        """
        if self._parent is None:
            raise TypeError("GenericIntrospectionMethod must be used as a class or instance attribute")
        return typing.cast(type[R], get_concrete_parent_argument(source or cls, self._parent, self._param, **self._update_kwargs(kwargs)))