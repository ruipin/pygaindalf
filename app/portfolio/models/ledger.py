# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import (override, Any, Iterator, TYPE_CHECKING,
    cast as typing_cast,
)
from pydantic import Field, computed_field, PrivateAttr
from collections.abc import MutableSequence, Sequence

from .instrument import Instrument
from .entity import AutomaticNamedEntity
from .entity.instance_store import NamedInstanceStoreEntityMixin
from .transaction import Transaction



class Ledger(MutableSequence, NamedInstanceStoreEntityMixin, AutomaticNamedEntity):
    # MARK: Instrument
    instrument: Instrument = Field(description="The financial instrument associated with this ledger, such as a stock, bond, or currency.")


    # MARK: Transactions
    # Make type checkers believe that the transactions sequence is mutable
    if TYPE_CHECKING:
        transactions_ : tuple[Transaction,...] = Field(default_factory=tuple, alias='transactions')
        @property
        def transactions(self) -> MutableSequence[Transaction]: ...
        @transactions.setter
        def transactions(self, value : MutableSequence[Transaction] | Sequence[Transaction]) -> None: ...
    else:
        transactions : tuple[Transaction,...] = Field(default_factory=tuple, description="A list of transactions associated with this ledger.")


    # MARK: Annotations
    #annotations: 'LedgerAnnotations'



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
        instrument_d = data.get('instrument', None)
        if isinstance(instrument_d, Instrument):
            instrument_name = instrument_d.instance_name
        elif isinstance(instrument_d, dict):
            instrument_name = Instrument.calculate_instance_name_from_dict(**instrument_d)
        else:
            raise TypeError(f"Expected 'instrument' to be an Instrument instance or a dict, got {type(instrument_d).__name__}.")

        return f"{cls.__name__}@{instrument_name}"

    @classmethod
    def by_instrument(cls, instrument: Instrument) -> 'Ledger | None':
        """
        Returns the ledger instance associated with the given instrument.
        If no ledger exists for the instrument, returns None.
        """
        if not isinstance(instrument, Instrument):
            raise TypeError(f"Expected 'instrument' to be an Instrument instance, got {type(instrument).__name__}.")

        result = cls.instance(instance_name=cls.calculate_instance_name_from_dict({'instrument': instrument}))
        if not isinstance(result, cls):
            raise TypeError(f"Expected 'result' to be an instance of {cls.__name__}, got {type(result).__name__}.")
        return result


    # MARK: Sequence ABC
    @override
    def __getitem__(self, index):
        return self.transactions[index]

    @override
    def __setitem__(self, index, value) -> None:
        self.transactions[index] = value

    @override
    def __delitem__(self, index) -> None:
        del self.transactions[index]

    @override
    def insert(self, index, value) -> None:
        self.transactions.insert(index, value)

    @override
    def __len__(self) -> int:
        return len(self.transactions)

    @computed_field(description="The number of transactions in the ledger.")
    @property
    def length(self) -> int:
        """
        Returns the number of transactions in the ledger.
        This is a computed property that provides the length of the transactions list.
        """
        return len(self.transactions)

    @override
    def __repr__(self) -> str:
        return super().__repr__().replace('>', f", transactions={repr(self.transactions)}>")