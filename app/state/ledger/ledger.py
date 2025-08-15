# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import override
from pydantic import Field

from ...util.mixins import LoggableHierarchicalMixin, NamedMixinMinimal
from ..uid import NamedUidMixin

from ..models.instrument import Instrument
from ..models.entity import AutomaticNamedEntity
from ..models.instance_store import NamedInstanceStoreModelMixin


class Ledger(NamedInstanceStoreModelMixin, AutomaticNamedEntity):
    # MARK: Fields
    instrument: Instrument = Field(description="The financial instrument associated with this ledger, such as a stock, bond, or currency.", json_schema_extra={'hierarchical': False})
    #transactions: List[Transaction]
    #annotations: 'LedgerAnnotations'


    # MARK: Instance Name
    @property
    @override
    def instance_name(self) -> str:
        return self.instrument.instance_name

    @classmethod
    @override
    def _convert_kwargs_to_instance_name(cls, **kwargs) -> str | None:
        """
        Convert the provided keyword arguments to an instance name.
        This method should be implemented by subclasses to define how to derive the instance name.
        """
        instrument_d = kwargs.get('instrument', None)
        if isinstance(instrument_d, Instrument):
            return instrument_d.instance_name
        elif isinstance(instrument_d, dict):
            return Instrument._convert_kwargs_to_instance_name(**instrument_d)
        else:
            raise TypeError(f"Expected 'instrument' to be an Instrument instance or a dict, got {type(instrument_d).__name__}.")

    # MARK: Methods
    #def add_transaction(self, tx: Transaction): ...
    #def replace_transaction(self, old_tx_id: str, new_tx: Transaction): ...
    #def edit_transaction(self, tx_id: str, actor: str): ...  # context manager