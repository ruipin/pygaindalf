# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from re import I
from pydantic import BaseModel, ConfigDict, ModelWrapValidatorHandler, ValidationInfo, model_validator, Field, field_validator, computed_field, model_validator
from typing import override, Any, ClassVar
from abc import abstractmethod, ABCMeta

from app.util.namespace.namespace import Self

from ...util.mixins import LoggableHierarchicalNamedModel, NamedMixin

from ..uid import Uid, UidMixinMinimal, NamedUidMixin, IncrementingUidMixin

from .meta_data import EntityMetaData




class Entity(UidMixinMinimal, LoggableHierarchicalNamedModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        #validate_assignment=True,
    )
    CHECK_DUPLICATE_UIDS : ClassVar[bool] = True  # Set to False to disable duplicate UID checks in EntityModel. This is potentially memory/performance intensive, so use with caution.
    UID_STORAGE : 'ClassVar[dict[Uid, Entity] | None]' = None  # Class variable to store UIDs of all instances of this class. Used to check for duplicate UIDs.

    meta : EntityMetaData = Field(default_factory=EntityMetaData, description="Metadata associated with the entity.", json_schema_extra={'keep_on_reinit': True})

    @computed_field(description="Unique identifier for the entity, automatically generated.")
    @property
    @override
    def uid(self) -> Uid:
        return super().uid

    def _validate_uid(self) -> Self:
        if self.uid is None:
            raise ValueError(f"{self.__class__.__name__} must have a valid UID. The UID cannot be None.")

        if self.__class__.CHECK_DUPLICATE_UIDS:
            uid_storage = self.__class__.UID_STORAGE
            if uid_storage is None:
                self.__class__.UID_STORAGE = uid_storage = {}
            existing = uid_storage.get(self.uid, None)
            if existing is not None and existing is not self:
                raise ValueError(f"Duplicate UID detected: {self.uid}. Each entity must have a unique UID.")
            uid_storage[self.uid] = self

        return self

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._validate_uid()

    @override
    def __hash__(self):
        return hash(self.uid)

class NamedEntity(NamedUidMixin, Entity):
    pass

class AutomaticNamedEntity(NamedEntity, metaclass=ABCMeta):
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance_name', None) is not None:
            raise ValueError(f"{self.__class__.__name__} does not support setting instance_name directly.")
        kwargs['instance_name'] = None
        super().__init__(*args, **kwargs)

    @property
    @override
    @abstractmethod
    def instance_name(self) -> str:
        raise NotImplementedError(f"{self.__class__.__name__} must implement instance_name property.")

class IncrementingUidEntity(IncrementingUidMixin, Entity):
    CHECK_DUPLICATE_UIDS : ClassVar[bool] = False  # IncrementingUidMixin cannot generate duplicate UIDs, so we always disable the check in this class.