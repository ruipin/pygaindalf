# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any

from ....util.helpers import mro
from ....util.models.uid import Uid
from .entity import Entity


if TYPE_CHECKING:
    from ..store import EntityStore
    from .entity_log import EntityLog


class IncrementingUidMixin(metaclass=ABCMeta):
    # MARK: Type hints for entity attributes and methods that we rely on
    if TYPE_CHECKING:
        uid: Uid
        entity_log: EntityLog

        @classmethod
        def _get_entity_store(cls) -> EntityStore: ...

        @classmethod
        def uid_namespace(cls) -> str: ...

        @classmethod
        def _calculate_instance_name(cls, data: Mapping[str, Any]) -> str: ...

    # MARK: Construction / metaclassing
    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        mro.ensure_mro_order(cls, IncrementingUidMixin, before=Entity)

    @classmethod
    def _calculate_uid(cls, data: Mapping[str, Any]) -> Uid:  # noqa: ARG003
        return cls._get_entity_store().generate_next_uid(cls.uid_namespace())

    @classmethod
    def calculate_instance_name_from_dict(cls, data: Mapping[str, Any]) -> str:
        uid = data.get("uid")
        if not isinstance(uid, Uid):
            msg = f"Expected 'uid' to be of type Uid, got {type(uid).__name__}."
            raise TypeError(msg)
        return str(uid)

    @classmethod
    def _calculate_instance_name_and_uid(cls, data: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        data["uid"] = cls._calculate_uid(data)
        data["instance_name"] = cls._calculate_instance_name(data)
        return data
