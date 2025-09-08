# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from typing import override, Any, overload, TYPE_CHECKING, Iterator, Iterable
from functools import cached_property
from pydantic import Field, computed_field, field_validator
from collections.abc import Set, MutableSet, Sequence

from ...collections.uid_proxy import UidProxyOrderedViewSet, UidProxySequence
from ...collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet

from ..instrument import Instrument
from ..entity import AutomaticNamedEntity
from ..entity.instance_store import NamedInstanceStoreEntityMixin
from ..transaction import Transaction, OrderedViewFrozenTransactionUidSet, UidProxyOrderedViewTransactionSet

from ..uid import Uid



class Ledger(NamedInstanceStoreEntityMixin, AutomaticNamedEntity, MutableSet[Transaction]):
    # MARK: Instrument
    instrument_uid: Uid = Field(description="The financial instrument associated with this ledger, such as a stock, bond, or currency.")

    @field_validator('instrument_uid', mode='before')
    @classmethod
    def _validate_instrument_uid(cls, value : Any):
        if not isinstance(value, Uid):
            raise TypeError(f"Expected 'instrument_uid' to be a Uid, got {type(value).__name__}.")
        if value.namespace != (instrument_ns := Instrument.uid_namespace()):
            raise ValueError(f"Invalid instrument UID namespace: expected '{instrument_ns}', got '{value.namespace}'.")
        return value

    @property
    def instrument(self) -> Instrument:
        entity = Instrument.by_uid(self.instrument_uid)
        if entity is None:
            raise ValueError(f"No instrument found for UID {self.instrument_uid}.")
        return entity



    # MARK: Instance Name
    @property
    @override
    def instance_name(self) -> str:
        instrument = getattr(self, 'instrument', None)
        if instrument is None:
            return f"{self.__class__.__name__}@None"
        return f"{self.__class__.__name__}@{self.instrument.instance_name}"

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        """
        Convert the provided keyword arguments to an instance name.
        This method should be implemented by subclasses to define how to derive the instance name.
        """
        instrument_uid = data.get('instrument_uid', None)
        if instrument_uid is None:
            raise TypeError(f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument_uid' in data to generate an instance name.")
        instrument = Instrument.by_uid(instrument_uid)
        if instrument is None:
            raise TypeError(f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument_uid' to correspond to a valid Instrument to generate an instance name.")
        instrument_name = instrument.instance_name
        if instrument_name is None:
            raise ValueError(f"Instrument with UID '{instrument_uid}' does not have a valid instance name.")

        return f"{cls.__name__}@{instrument_name}"

    @classmethod
    def by_instrument(cls, instrument: Instrument) -> Ledger | None:
        """
        Returns the ledger instance associated with the given instrument.
        If no ledger exists for the instrument, returns None.
        """
        if not isinstance(instrument, Instrument):
            raise TypeError(f"Expected 'instrument' to be an Instrument instance, got {type(instrument).__name__}.")

        result = cls.instance(instance_name=cls.calculate_instance_name_from_dict({'instrument_uid': instrument.uid}))
        if not isinstance(result, cls):
            raise TypeError(f"Expected 'result' to be an instance of {cls.__name__}, got {type(result).__name__}.")
        return result



    # MARK: Transactions
    # Make type checkers believe that the transaction_uids tuple is mutable
    if TYPE_CHECKING:
        transaction_uids_ : Iterable[Uid] = Field(default_factory=OrderedViewFrozenTransactionUidSet, alias='transaction_uids')
        @property
        def transaction_uids(self) -> OrderedViewSet[Uid]: ...
        @transaction_uids.setter
        def transaction_uids(self, value : MutableSet[Uid] | Set[Uid]) -> None: ...
    else:
        transaction_uids : OrderedViewFrozenTransactionUidSet = Field(default_factory=OrderedViewFrozenTransactionUidSet, description="A set of transaction Uids associated with this ledger.")

    @cached_property
    def transactions(self) -> UidProxyOrderedViewTransactionSet:
        return UidProxyOrderedViewTransactionSet(owner=self, field='transaction_uids')


    # MARK: Custom __getitem__
    def __getitem__(self, index : int | Uid) -> Transaction:
        if isinstance(index, int):
            return self.transactions[index]

        elif isinstance(index, Uid):
            if index not in self.transaction_uids:
                raise KeyError(f"Transaction with UID {index} not found in ledger")
            if (transaction := Transaction.by_uid(index)) is None:
                raise KeyError(f"Transaction with UID {index} not found")
            return transaction

        else:
            raise KeyError(f"Index must be an int or Uid, got {type(index).__name__}")


    # MARK: MutableSet ABC
    @override
    def __contains__(self, value : object) -> bool:
        if not isinstance(value, (Transaction, Uid)):
            return False
        return Transaction.narrow_to_uid(value) in self.transaction_uids

    @override
    def add(self, value : Transaction | Uid) -> None:
        self.transaction_uids.add(Transaction.narrow_to_uid(value))

    @override
    def discard(self, value : Transaction | Uid) -> None:
        self.transaction_uids.discard(Transaction.narrow_to_uid(value))

    @override
    def __iter__(self) -> Iterator[Transaction]: # pyright: ignore[reportIncompatibleMethodOverride] since we are overriding the pydantic.BaseModel iterator on purpose
        # TODO: Wrap an ordered view
        for uid in self.transaction_uids:
            transaction = Transaction.by_uid(uid)
            if transaction is None:
                raise KeyError(f"Transaction with UID {uid} not found")
            yield transaction

    @override
    def __len__(self):
        return len(self.transaction_uids)

    @property
    def length(self) -> int:
        return len(self.transaction_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f", transactions={repr(self.transaction_uids)}>")