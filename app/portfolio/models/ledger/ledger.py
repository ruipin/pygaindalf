# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime

from typing import override, Any, overload, TYPE_CHECKING, Iterator, Iterable
from functools import cached_property
from pydantic import Field, computed_field, field_validator
from collections.abc import Set, MutableSet, Sequence

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison

from ...collections.uid_proxy import UidProxyOrderedViewSet, UidProxySequence
from ...collections.ordered_view import OrderedViewSet, OrderedViewFrozenSet

from ..instrument.instrument import Instrument
from ..entity.instance_store import NamedInstanceStoreEntityMixin
from ..entity import Entity
from ..transaction import Transaction, OrderedViewFrozenTransactionUidSet, UidProxyOrderedViewTransactionFrozenSet

from ..uid import Uid

from .ledger_base import LedgerBase
from .ledger_journal import LedgerJournal



class Ledger(LedgerBase, NamedInstanceStoreEntityMixin, Entity[LedgerJournal]):
    @classmethod
    @override
    def get_journal_class(cls) -> type[LedgerJournal]:
        return LedgerJournal



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
        return Instrument.by_uid(self.instrument_uid)



    # MARK: Instance Name
    @property
    @override
    def instance_name(self) -> str:
        return self.calculate_instance_name_from_dict(self.__dict__, allow_missing_instrument=True)

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data : dict[str, Any], allow_missing_instrument : bool = False) -> str:
        """
        Convert the provided keyword arguments to an instance name.
        This method should be implemented by subclasses to define how to derive the instance name.
        """
        instrument_uid = data.get('instrument_uid', None)
        if instrument_uid is None:
            raise TypeError(f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument_uid' in data to generate an instance name.")
        instrument = Instrument.by_uid_or_none(instrument_uid)
        if instrument is None:
            if not allow_missing_instrument:
                raise TypeError(f"{cls.__name__}.calculate_instance_name_from_dict requires 'instrument_uid' to correspond to a valid Instrument to generate an instance name.")
            instrument_name = 'None'
        else:
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
    if TYPE_CHECKING:
        transaction_uids : Set[Uid] = Field(default_factory=frozenset)
    else:
        transaction_uids : OrderedViewFrozenTransactionUidSet = Field(default_factory=OrderedViewFrozenTransactionUidSet, description="A set of transaction Uids associated with this ledger.")

    @cached_property
    def transactions(self) -> UidProxyOrderedViewTransactionFrozenSet:
        return UidProxyOrderedViewTransactionFrozenSet(owner=self, field='transaction_uids')


    # MARK: Utilities
    @override
    def sort_key(self) -> SupportsRichComparison:
        return (self.instance_name, self.uid)