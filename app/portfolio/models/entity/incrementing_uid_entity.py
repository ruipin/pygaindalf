# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import ClassVar, override, Any
from pydantic import computed_field

from ....util.helpers import script_info

from ..uid import IncrementingUidFactory, Uid

from .named_entity import AutomaticNamedEntity
from .entity import Entity


class IncrementingUidEntity(AutomaticNamedEntity):
    _UID_FACTORY : ClassVar[IncrementingUidFactory]

    if script_info.is_unit_test():
        @classmethod
        @override
        def reset_state(cls) -> None:
            super().reset_state()
            if hasattr(cls, '_UID_FACTORY'):
                cls._UID_FACTORY.reset()

    def __init_subclass__(cls) -> None:
        """
        Initialize the mixin for subclasses.
        This ensures that the UID factory is created only once per class.
        """
        if getattr(cls, '_UID_FACTORY', None) is None:
            cls._UID_FACTORY = IncrementingUidFactory()

    @classmethod
    @override
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        return cls._UID_FACTORY.next(cls.uid_namespace(data))

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data : dict[str, Any]) -> str:
        uid = data.get('uid', None)
        if not isinstance(uid, Uid):
            raise TypeError(f"Expected 'uid' to be of type Uid, got {type(uid).__name__}.")
        return str(uid)

    @property
    @override
    def instance_name(self) -> str:
        return str(self.uid)