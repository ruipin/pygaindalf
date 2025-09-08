# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import typing, types, annotationlib


# MARK: Definitions
type GenericAlias = types.GenericAlias | typing._GenericAlias # pyright: ignore[reportAttributeAccessIssue] as typing._GenericAlias does exist, but is undocumented

class GenericsError(TypeError):
    pass


# MARK: get_bases
def get_original_bases(cls : type | GenericAlias) -> tuple[typing.Any, ...]:
    if not isinstance(cls, type):
        _cls = typing.get_origin(cls)
        if _cls is None:
            raise GenericsError(f"{cls} is not a generic class")
        cls = _cls

    return types.get_original_bases(cls)


# MARK: get_arg_info
def get_arg_info(cls : type | GenericAlias, name : str) -> tuple[int, typing.TypeVar]:
    bases = get_original_bases(cls)
    for base in bases:
        origin = typing.get_origin(base) or base
        args = typing.get_args(base)
        if origin is typing.Generic:
            generic = base
            break
    else:
        raise GenericsError(f"{cls.__name__} is not a generic class")
    args = typing.get_args(generic)

    for index, arg in enumerate(args):
        if arg.__name__ == name:
            return (index, arg)

    raise GenericsError(f"Could not find generic argument {name} in {cls.__name__}")


# MARK: has_arg
def has_arg(cls : type | GenericAlias, name : str) -> bool:
    try:
        get_arg(cls, name)
        return True
    except GenericsError as e:
        return False



# MARK: get_arg / get_concrete_arg
def get_arg(cls : GenericAlias, name : str) -> typing.TypeVar | type | GenericAlias:
    # Get index and TypeVar for the named generic argument
    (index, generic) = get_arg_info(cls, name)
    if generic is None:
        raise RuntimeError(f"Could not find generic argument {name} in {cls.__name__}")
    bound = annotationlib.call_evaluate_function(generic.evaluate_bound, format=annotationlib.Format.FORWARDREF) if generic.evaluate_bound else None

    # Get the actual type argument at that index
    args = typing.get_args(cls)
    if len(args) <= index:
        raise GenericsError(f"Expected at least {index+1} type arguments for {cls.__name__}, got {len(args)}")

    # Return the type argument, checking it against the bound if any
    arg = args[index]
    if isinstance(arg, typing.TypeVar):
        return arg

    if isinstance(bound, (str, typing.ForwardRef)):
        return arg
    if bound is not None:
        arg_origin = typing.get_origin(arg) or arg
        bound_origin = typing.get_origin(bound) or bound
        if not issubclass(arg_origin, bound_origin):
            raise TypeError(f"{cls.__name__}.{name} type argument <{arg.__name__}> is not a subclass of its bound <{bound.__name__}>")

    return arg

def get_concrete_arg(cls : GenericAlias, name : str) -> type:
    arg = get_arg(cls, name)
    if isinstance(arg, typing.TypeVar):
        raise GenericsError(f"Could not resolve {cls.__name__}.{name} type argument to a concrete type")
    origin = arg if isinstance(arg, type) else typing.get_origin(arg)
    if origin is None:
        raise GenericsError(f"{cls.__name__}.{name} type argument is not a generic type, got <{arg.__name__}>")
    return origin



# MARK: get_bases_between
def get_bases_between[T : type](cls : T, parent : T, result : list[T] | None = None) -> list[T]:
    if result is None:
        result = []

    result.append(cls)

    bases = get_original_bases(cls)
    for base in bases:
        origin = typing.get_origin(base) or base
        if origin is None:
            continue

        if origin is parent:
            if origin is not base:
                result.append(base)
            return result

        if issubclass(origin, parent):
            return get_bases_between(base, parent, result)

    raise GenericsError(f"{cls.__name__} is not a subclass of {parent.__name__}")


# MARK: get_parent_arg / get_concrete_parent_arg
def get_parent_arg[T : type](cls : T, parent : T, name : str) -> T | typing.TypeVar | GenericAlias:
    bases = get_bases_between(cls, parent)
    if not bases:
        raise GenericsError(f"{cls.__name__} is not a subclass of {parent.__name__}")

    arg = None
    for base in reversed(bases):
        if arg is None:
            arg = get_arg(base, name)
        else:
            if not isinstance(arg, typing.TypeVar):
                raise GenericsError(f"Could not resolve {base.__name__}'s {parent.__name__}.{name} type argument {arg}")

            if not has_arg(base, arg.__name__):
                return arg

            arg = get_arg(base, arg.__name__)

        if isinstance(arg, typing.TypeVar):
            continue

        return typing.cast(T, arg)

    return typing.cast(T, arg)

def get_concrete_parent_arg[T : type](cls : T, parent : T, name : str) -> type:
    arg = get_parent_arg(cls, parent, name)
    if isinstance(arg, typing.TypeVar):
        raise GenericsError(f"Could not resolve {cls.__name__}.{name} type argument to a concrete type")
    origin = arg if isinstance(arg, type) else typing.get_origin(arg)
    if origin is None:
        raise GenericsError(f"{cls.__name__}.{name} type argument is not a generic type, got {arg}")
    return origin