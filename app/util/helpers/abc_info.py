# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Helpers for inspecting abstract base classes (ABCs).

This module centralises metadata needed to reason about runtime ABCs and the
standard collection ABC hierarchy. It provides:

* curated lists of supported ABC types and commonly used concrete bases,
* pre-computed lookup tables for quickly mapping between ABCs and compatible
  base classes, and
* high-level helpers that resolve the concrete key/value types declared by
  generic collections or inferred from a concrete instance.

String-like sequences such as ``str`` and ``bytes`` are explicitly represented
in :const:`SUPPORTED_ABCS` so callers can detect when string literals are being
treated as collections in generic code paths.

The resolved information is exposed via :class:`ABCInfo`, an immutable structure
that provides convenient properties for inspecting the collection's capabilities
and declared key/value types.

Examples
========

*1. Inspect a built-in mapping instance*

    >>> from app.util.helpers import abc_info
    >>> info = abc_info.get_abc_info([1, 2, 3])
    >>> info.sequence
    True
    >>> info.mutable
    True

*2. Resolve collection metadata from class annotations*

    >>> class ContainsMapping:
    ...     data : dict[str, float]
    >>> info = abc_info.get_class_attribute_abc_info(ContainsMapping, "data")
    >>> info.mapping
    True
    >>> info.key_type
    <class 'str'>
    >>> info.value_type
    <class 'float'>
"""

import typing

from collections import abc as abcs
from frozendict import frozendict

from . import generics
from . import type_hints


# MARK: Definitions
#: Union of ABC classes and built-in string-like types understood by the helpers.
type ABCType = abcs.Container | abcs.Iterator | abcs.Iterable | abcs.Reversible | abcs.Generator | abcs.Hashable | abcs.Sized | type[str] | type[bytes]



# MARK: ABC Lookup Info & Mappings
#: Ordered list of ABC types analysed during lookup, including ``str`` and ``bytes``
#: so callers can easily distinguish literal-like sequences from general collections.
SUPPORTED_ABCS: tuple[type[ABCType], ...] = (
    abcs.Hashable, abcs.Sized, abcs.Container, abcs.Reversible,
    abcs.Iterable, abcs.Iterator, abcs.Generator,
    abcs.Mapping, abcs.MutableMapping,
    abcs.Set, abcs.MutableSet,
    abcs.Sequence, abcs.MutableSequence,
    str, bytes,
)

#: Concrete builtin bases tested when deriving key/value arguments for ABCs.
SUPPORTED_BASES: tuple[type, ...] = (
    dict, #frozendict,
    list, tuple,
    frozenset, set,
    str, bytes,
)

class ABCLookupInfo(typing.NamedTuple):
    """Runtime metadata describing an ABC and its related concrete bases."""

    #: Primary abstract base class inspected for compatibility.
    abc: type[ABCType]
    #: All ABCs satisfied by the primary ABC through inheritance.
    abcs: tuple[type[ABCType], ...]
    #: Built-in concrete types that may implement the ABC.
    possible_bases: tuple[type, ...]

def _prepare_mappings() -> abcs.Mapping[type, ABCLookupInfo]:
    """Build the immutable lookup table mapping ABCs to compatible bases."""
    mapping = {}

    for abc in SUPPORTED_ABCS:
        abcs_list = []
        bases = []

        for supported in SUPPORTED_ABCS:
            if issubclass(abc, supported): # pyright: ignore[reportGeneralTypeIssues]
                abcs_list.append(supported)
                bases.append(supported)

        for base in SUPPORTED_BASES:
            if issubclass(base, abc):
                bases.append(base)

        mapping[abc] = ABCLookupInfo(
            abc = abc,
            abcs = tuple(abcs_list),
            possible_bases = tuple(bases),
        )

    return frozendict(mapping)

#: Immutable mapping from supported ABCs to their lookup metadata.
ABC_MAPPINGS = _prepare_mappings()



# MARK: ABC Info
class ABCInfo(typing.NamedTuple):
    """Detailed information about a collection ABC or concrete collection type."""

    #: Source runtime type or generic alias inspected for ABC details.
    source: type | generics.GenericAlias
    #: Lookup metadata describing the ABC hierarchy and possible bases.
    lookup: ABCLookupInfo
    #: Concrete or generic alias describing the key type if applicable.
    key_type: type | generics.GenericAlias | typing.ForwardRef | None
    #: Concrete or generic alias describing the value type if applicable.
    value_type: type | generics.GenericAlias | typing.ForwardRef | None

    @property
    def source_origin(self) -> type:
        """Return the non-aliased origin for :attr:`source`."""
        return generics.get_origin(self.source, passthrough=True)

    @property
    def has_key(self) -> bool:
        """Return ``True`` when the collection describes explicit key types."""
        return self.key_type is not None

    @property
    def key_origin(self) -> type | None:
        """Return the origin type for the declared key if one exists."""
        if not self.has_key:
            return None
        return generics.get_origin(self.key_type, passthrough=True)

    @property
    def key_concrete(self) -> bool:
        """Return ``True`` when the key type is a concrete type and not a type variable or forward reference."""
        if not self.has_key:
            return False
        return isinstance(self.key_type, type)

    @property
    def has_value(self) -> bool:
        """Return ``True`` when the collection exposes a derived value type."""
        return self.value_type is not None

    @property
    def value_origin(self) -> type | None:
        """Return the origin type for the declared value if one exists."""
        if not self.has_value:
            return None
        return generics.get_origin(self.value_type, passthrough=True)

    @property
    def value_concrete(self) -> bool:
        """Return ``True`` when the value type is a concrete type and not a type variable or forward reference."""
        if not self.has_value:
            return False
        return isinstance(self.value_type, type)

    @property
    def specialized(self) -> bool:
        """Return ``True`` when the collection is specialised with value types."""
        has_value = self.has_value
        assert not has_value or self.has_key or not self.mutable
        return has_value

    @classmethod
    def create(cls, abc : ABCType) -> ABCInfo:
        """Construct :class:`ABCInfo` directly from an ABC instance."""
        return get_abc_info(abc)

    @property
    def abc(self) -> type[ABCType]:
        """Return the primary ABC associated with this info entry."""
        return self.lookup.abc

    @property
    def abcs(self) -> tuple[type[ABCType],...]:
        """Return all ABCs satisfied by :attr:`source`."""
        return self.lookup.abcs

    def matches(self, abc : type[ABCType] | tuple[ABCType,...]) -> bool:
        """Return whether the info is compatible with the supplied ABC(s)."""
        for klass in (abc,) if isinstance(abc, type) else abc:
            if klass in self.abcs:
                return True
        return False

    @property
    def mutable(self) -> bool:
        """Return ``True`` when the collection advertises mutable semantics."""
        return self.matches((abcs.MutableMapping, abcs.MutableSet, abcs.MutableSequence))

    @property
    def sequence(self) -> bool:
        """Return ``True`` for sequence-like collections."""
        return self.matches(abcs.Sequence)

    @property
    def mapping(self) -> bool:
        """Return ``True`` for mapping-like collections."""
        return self.matches(abcs.Mapping)

    @property
    def set(self) -> bool:
        """Return ``True`` for set-like collections."""
        return self.matches(abcs.Set)

    @property
    def container(self) -> bool:
        """Return ``True`` if the collection satisfies :class:`collections.abc.Container`."""
        return self.matches(abcs.Container) # pyright: ignore[reportArgumentType]

    @property
    def iterable(self) -> bool:
        """Return ``True`` if the collection satisfies :class:`collections.abc.Iterable`."""
        return self.matches(abcs.Iterable) # pyright: ignore[reportArgumentType]

    @property
    def iterator(self) -> bool:
        """Return ``True`` if the collection satisfies :class:`collections.abc.Iterator`."""
        return self.matches(abcs.Iterator) # pyright: ignore[reportArgumentType]

    @property
    def generator(self) -> bool:
        """Return ``True`` if the collection satisfies :class:`collections.abc.Generator`."""
        return self.matches(abcs.Generator) # pyright: ignore[reportArgumentType]

    @property
    def hashable(self) -> bool:
        """Return ``True`` if the collection satisfies :class:`collections.abc.Hashable`."""
        return self.matches(abcs.Hashable) # pyright: ignore[reportArgumentType]

    @property
    def str_or_bytes(self) -> bool:
        """Return ``True`` if the collection is either :class:`str` or :class:`bytes`."""
        return self.abc in (str, bytes)




# MARK: Internal API
@typing.overload
def _get_abc_info(*, abc : type[ABCType] | ABCType, namespace : object, attr : str) -> ABCInfo: ...
@typing.overload
def _get_abc_info(*, abc : type[ABCType] | ABCType, namespace : None = None, attr : None = None) -> ABCInfo: ...
@typing.overload
def _get_abc_info(*, abc : None = None, namespace : object, attr : str) -> ABCInfo | None: ...

def _get_abc_info(*, abc : type[ABCType] | ABCType | None = None, namespace : object | None = None, attr : str | None = None) -> ABCInfo | None:
    """Resolve :class:`ABCInfo` from either a concrete ABC or cached type hints.

    Args:
        abc: An optional collection instance whose type is inspected directly.
        namespace: A namespace (class, module, object, etc) containing the attribute *attr* for type hint lookups.
        attr: The attribute name to inspect on *cls*.

    Returns:
        The resolved :class:`ABCInfo`, or ``None`` when the type cannot be
        categorised as one of the supported ABCs.
    """
    # Validate parameters
    if abc is None:
        if namespace is None or attr is None:
            raise ValueError("If abc is not provided, both namespace and attr must be provided.")
    if attr is not None:
        if namespace is None:
            raise ValueError("If attr is provided, namespace must also be provided.")
        assert isinstance(attr, str)
    if namespace is not None:
        if attr is None:
            raise ValueError("If namespace is provided, attr must also be provided.")
        assert isinstance(namespace, object)

    # Find the type for this field, if any - either from the actual collection or from type hints
    if abc is None:
        typ = None
    elif isinstance(abc, type):
        typ = abc
    else:
        typ = type(abc)

    if namespace is not None and attr is not None:
        if (type_hint := type_hints.get_type_hints(namespace).get(attr, None)) is not None:
            if typ is not None:
                typ = type_hints.match_type_hint(typ or object, type_hint)
            else:
                if isinstance(type_hint, typing.Union):
                    raise NotImplementedError("Union type hints not supported when abc is None")
                typ = type_hint

    if typ is None:
        return None

    # Figure out what type of collection this is, and try to get the value type
    origin = generics.get_origin(typ, passthrough=True)

    key_type = None
    value_type = None
    has_key = False
    if issubclass(origin, abcs.Container):
        if issubclass(origin, abcs.Mapping):
            has_key = True
            if issubclass(origin, abcs.MutableMapping):
                lookup = ABC_MAPPINGS[abcs.MutableMapping]
            else:
                lookup = ABC_MAPPINGS[abcs.Mapping]
        elif issubclass(origin, abcs.Set):
            if issubclass(origin, abcs.MutableSet):
                lookup = ABC_MAPPINGS[abcs.MutableSet]
            else:
                lookup = ABC_MAPPINGS[abcs.Set]
        elif issubclass(origin, abcs.Sequence):
            if issubclass(origin, abcs.MutableSequence):
                lookup = ABC_MAPPINGS[abcs.MutableSequence]
            elif issubclass(origin, (str, bytes)):
                value_type = str if issubclass(origin, str) else bytes
                lookup = ABC_MAPPINGS[value_type]
            else:
                lookup = ABC_MAPPINGS[abcs.Sequence]
        else:
            lookup = ABC_MAPPINGS[abcs.Container]
    elif issubclass(origin, abcs.Iterable):
        if issubclass(origin, abcs.Iterator):
            if issubclass(origin, abcs.Generator):
                lookup = ABC_MAPPINGS[abcs.Generator]
            else:
                lookup = ABC_MAPPINGS[abcs.Iterator]
        else:
            lookup = ABC_MAPPINGS[abcs.Iterable]
    elif issubclass(origin, abcs.Hashable):
        lookup = ABC_MAPPINGS[abcs.Hashable]
    else:
        return None

    # Instrospect key type
    if key_type is None and has_key:
        key_arg_info = generics.get_parent_argument_info_or_none(typ, lookup.possible_bases, 0)
        if key_arg_info is not None:
            key_type = key_arg_info.value_or_bound

    # Introspect value type
    if value_type is None:
        value_arg_info = generics.get_parent_argument_info_or_none(typ, lookup.possible_bases, 1 if has_key else 0)
        if value_arg_info is not None:
            value_type = value_arg_info.value_or_bound

    # TODO: Optionally iterate the collection and collect concrete types if generics are not available

    return ABCInfo(
        source     = typ,
        lookup     = lookup,
        key_type   = key_type,
        value_type = value_type,
    )



# MARK: Public API
@typing.overload
def get_abc_info(abc : type[ABCType] | ABCType, *, namespace : object, attr : str) -> ABCInfo: ...
@typing.overload
def get_abc_info(abc : type[ABCType] | ABCType, *, namespace : None = None, attr : None = None) -> ABCInfo: ...

def get_abc_info(abc : type[ABCType] | ABCType, *, namespace : object | None = None, attr : str | None = None) -> ABCInfo:
    """Public wrapper around :func:`_get_abc_info` that always returns an entry."""
    return _get_abc_info(abc=abc, namespace=namespace, attr=attr) # pyright: ignore[reportCallIssue, reportArgumentType]

def get_class_attribute_abc_info(namespace : object, attr : str) -> ABCInfo | None:
    """Return :class:`ABCInfo` for a cached collection attribute on *cls* if known."""
    return _get_abc_info(abc=None, namespace=namespace, attr=attr)