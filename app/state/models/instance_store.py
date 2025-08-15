# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pydantic import model_validator, BaseModel, ModelWrapValidatorHandler
from typing import Any, Self, ClassVar, override
from abc import ABCMeta, abstractmethod

from ...util.mixins import NamedProtocol


class InstanceStoreModelMixin(metaclass=ABCMeta):
    # MARK: Abstract Methods
    @classmethod
    @abstractmethod
    def _instance_store_search(cls, **kwargs) -> Self | None:
        raise NotImplementedError("This method should be implemented by subclasses to find an existing instance based on the provided kwargs.")

    @classmethod
    @abstractmethod
    def _instance_store_add(cls, instance: Self) -> None:
        raise NotImplementedError("This method should be implemented by subclasses to add an instance to the store.")


    # MARK: Create instance
    def __new__(cls, **kwargs):
        instance = cls._instance_store_search(**kwargs)
        if instance:
            return instance
        else:
            return super().__new__(cls)


    # MARK: Handle (re-)initialization
    @model_validator(mode='wrap')
    @classmethod
    def _validate_singleton(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not issubclass(cls, BaseModel):
            raise TypeError(f"{cls.__name__} must be a subclass of BaseModel to use InstanceStoreModelMixin.")

        if isinstance(data, cls):
            return data

        if not isinstance(data, dict):
            raise TypeError(f"Expected a dictionary for {cls.__name__}, got {type(data).__name__}.")

        instance = cls._instance_store_search(**data)

        old_dict : dict[str, Any] | None = None
        if instance is not None:
            old_dict = dict()
            for fld, info in cls.model_fields.items():
                instance_has_fld = fld in instance.__dict__
                data_has_fld = fld in data

                extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else None
                keep_on_reinit = extra.get('keep_on_reinit', False) if extra else False

                if instance_has_fld and (not data_has_fld or keep_on_reinit):
                    if data_has_fld and keep_on_reinit:
                        raise ValueError(f"Field '{fld}' is present in both the data and the existing instance of {cls.__name__}, but 'keep_on_reinit' is set to True. This field should not be re-initialized.")
                    data[fld] = instance.__dict__[fld]
                elif data_has_fld and not instance_has_fld:
                    raise ValueError(f"Field '{fld}' is not present in the existing instance of {cls.__name__}.")
                elif instance_has_fld:
                    old_dict[fld] = instance.__dict__[fld]

        result = handler(data)

        if not isinstance(result, cls):
            raise TypeError(f"Expected {cls.__name__} instance, got {type(result).__name__}.")

        if old_dict is not None:
            try:
                for key, value in old_dict.items():
                    result_value = getattr(result, key, None)
                    if isinstance(result_value, object):
                        if value is not result_value:
                            raise ValueError(f"Re-initialization of {cls.__name__} changed the instance's attribute object '{key}': {value} -> {result_value}")
                    else:
                        if value != result_value:
                            raise ValueError(f"Re-initialization of {cls.__name__} changed the instance's attribute '{key}': {value} -> {result_value}")
            finally:
                result.__dict__.update(old_dict)

        cls._instance_store_add(result)

        return result



# MARK: Mixin for Named Instances
class NamedInstanceStoreModelMixin(InstanceStoreModelMixin, metaclass=ABCMeta):
    INSTANCES : ClassVar[dict[str, InstanceStoreModelMixin]] = {}

    @classmethod
    @override
    def _instance_store_search(cls, **kwargs) -> InstanceStoreModelMixin | None:
        instance_name = cls._convert_kwargs_to_instance_name(**kwargs)
        if instance_name is None:
            return None
        return cls.INSTANCES.get(instance_name, None)

    @classmethod
    @override
    def _instance_store_add(cls, instance: InstanceStoreModelMixin) -> None:
        if not isinstance(instance, NamedProtocol):
            raise TypeError(f"Expected an instance of a class implementing NamedProtocol, got {type(instance).__name__}.")
        cls.INSTANCES[instance.instance_name] = instance

    @classmethod
    def instance(cls, instance_name: str) -> InstanceStoreModelMixin | None:
        return cls.INSTANCES.get(instance_name)

    @classmethod
    @abstractmethod
    def _convert_kwargs_to_instance_name(cls, **kwargs) -> str | None:
        """
        Convert the provided keyword arguments to an instance name.
        This method should be implemented by subclasses to define how to derive the instance name.
        """
        raise NotImplementedError("This method should be implemented by subclasses to convert kwargs to an instance name.")