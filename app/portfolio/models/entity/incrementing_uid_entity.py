# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import ClassVar, override, Any
from pydantic import computed_field

from ....util.helpers import script_info

from ..uid import IncrementingUidFactory, Uid

from .named_entity import AutomaticNamedEntity
from .entity import Entity


class IncrementingUidEntity(AutomaticNamedEntity):
    @classmethod
    @override
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        return cls._get_entity_store().generate_next_uid(cls.uid_namespace(data))

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