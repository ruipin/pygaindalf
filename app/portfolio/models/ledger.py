# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override, Any, overload, Iterable, TYPE_CHECKING
from functools import cached_property
from pydantic import Field, computed_field, field_validator
from collections.abc import Sequence, MutableSequence

from ..collections.uid_proxy.sequence import UidProxySequence

from .instrument import Instrument
from .entity import AutomaticNamedEntity
from .entity.instance_store import NamedInstanceStoreEntityMixin
from .transaction import Transaction

from .uid import Uid


# Specialize explicitly in order for type introspection to work
class UidProxyTransactionSequence(UidProxySequence[Transaction]):
    pass


class Ledger(MutableSequence[Transaction], NamedInstanceStoreEntityMixin, AutomaticNamedEntity):
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


    # MARK: Transactions
    # Make type checkers believe that the transaction_uids tuple is mutable
    if TYPE_CHECKING:
        transaction_uids_ : tuple[Uid,...] = Field(default_factory=tuple, alias='transaction_uids')
        @property
        def transaction_uids(self) -> MutableSequence[Uid]: ...
        @transaction_uids.setter
        def ledgers(self, value : MutableSequence[Uid] | Sequence[Uid]) -> None: ...
    else:
        transaction_uids : tuple[Uid,...] = Field(default_factory=tuple, description="A list of transaction Uids associated with this ledger.")

    @field_validator('transaction_uids', mode='before')
    @classmethod
    def _validate_transaction_uids(cls, value : Any):
        if not isinstance(value, Sequence):
            raise TypeError(f"Expected 'transaction_uids' to be a Sequence, got {type(value).__name__}.")

        transaction_ns = Transaction.uid_namespace()
        for uid in value:
            if not isinstance(uid, Uid):
                raise TypeError(f"Expected 'transaction_uids' elements to be Uid instances, got {type(uid).__name__}.")
            if not uid.namespace.startswith(transaction_ns):
                raise ValueError(f"Invalid transaction UID namespace: expected it to start with '{transaction_ns}', got '{uid.namespace}'.")

        return value

    @cached_property
    def transactions(self) -> MutableSequence[Transaction]:
        return UidProxyTransactionSequence(owner=self, field='transaction_uids')



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
    def by_instrument(cls, instrument: Instrument) -> 'Ledger | None':
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



    # MARK: MutableSequence ABC
    @overload
    def __getitem__(self, index: int) -> Transaction: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[Transaction]: ...
    @override
    def __getitem__(self, index) -> Transaction | MutableSequence[Transaction]:
        return self.transactions[index]

    @overload
    def __setitem__(self, index: int, value: Transaction) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[Transaction]) -> None: ...
    @override
    def __setitem__(self, index: int | slice, value: Transaction | Iterable[Transaction]) -> None:
        self.transactions[index] = value # pyright: ignore[reportCallIssue, reportArgumentType] as the overloads make this type safe

    @overload
    def __delitem__(self, index: int) -> None: ...
    @overload
    def __delitem__(self, index: slice) -> None: ...
    @override
    def __delitem__(self, index: int | slice) -> None:
        del self.transaction_uids[index]

    @override
    def insert(self, index: int, value: Transaction) -> None:
        self.transaction_uids.insert(index, value.uid)

    @override
    def __len__(self) -> int:
        return len(self.transaction_uids)

    @computed_field(description="The number of transactions in the ledger.")
    @property
    def length(self) -> int:
        """
        Returns the number of transactions in the ledger.
        This is a computed property that provides the length of the transactions list.
        """
        return len(self.transaction_uids)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f", transactions={repr(self.transaction_uids)}>")