# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from typing import TYPE_CHECKING, Any, override

from ....util.helpers import mro
from ...journal.entity_journal import EntityJournal
from ...util.uid import UID_SEPARATOR, Uid
from .entity import Entity


if TYPE_CHECKING:
    from .entity_proxy import EntityProxy


class IncrementingUidEntityMixin(Entity if TYPE_CHECKING else object, metaclass=ABCMeta):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        mro.ensure_mro_order(cls, IncrementingUidEntityMixin, before=Entity)

    @classmethod
    @override
    def _calculate_uid(cls, data: dict[str, Any]) -> Uid:
        return cls._get_entity_store().generate_next_uid(cls.uid_namespace())

    @classmethod
    @override
    def calculate_instance_name_from_dict(cls, data: dict[str, Any]) -> str:
        uid = data.get("uid")
        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)
        return str(uid)

    @property
    @override
    def instance_name(self) -> str:
        try:
            return str(self.uid)
        except Exception:  # noqa: BLE001 as we want to ensure we can use this in exception messages
            return f"{type(self).__name__}{UID_SEPARATOR}<invalid-uid>"


class IncrementingUidEntity[T_Journal: EntityJournal, T_Proxy: EntityProxy](IncrementingUidEntityMixin, Entity[T_Journal, T_Proxy], metaclass=ABCMeta):
    pass
