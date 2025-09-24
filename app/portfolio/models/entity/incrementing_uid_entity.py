# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import override, Any, TYPE_CHECKING
from abc import ABCMeta

from ....util.helpers import mro
from ...journal.entity_journal import EntityJournal
from ..uid import Uid
from .entity import Entity


class IncrementingUidEntityMixin(Entity if TYPE_CHECKING else object, metaclass=ABCMeta):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        mro.ensure_mro_order(cls, IncrementingUidEntityMixin, before=Entity)

    @classmethod
    @override
    def _calculate_uid(cls, data : dict[str, Any]) -> Uid:
        return cls._get_entity_store().generate_next_uid(cls.uid_namespace())

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


class IncrementingUidEntity[T_Journal2 : EntityJournal](IncrementingUidEntityMixin, Entity[T_Journal2], metaclass=ABCMeta):
    pass