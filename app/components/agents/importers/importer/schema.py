# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


import importlib

from abc import ABCMeta
from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, override
from typing import cast as typing_cast

from frozendict import frozendict
from pydantic import ConfigDict, Field, field_validator

from .....portfolio.models.annotation import Annotation
from .....portfolio.models.instrument import Instrument, InstrumentSchema
from .....portfolio.models.ledger import Ledger
from .....portfolio.models.transaction import Transaction, TransactionSchema
from .....util.config import BaseConfigModel
from .....util.helpers.decimal_currency import DecimalCurrency
from .....util.models.hierarchical import HierarchicalModel
from .....util.models.uid import Uid
from .importer import Importer, ImporterConfig


if TYPE_CHECKING:
    from .....portfolio.models.entity import Entity
    from .....util.helpers.currency import Currency


# MARK: Schema Classes
class ImportData(BaseConfigModel):
    uid: Uid | None = Field(default=None, description="The unique identifier for the imported object")
    annotations: "tuple[AnnotationImportData, ...]" = Field(default_factory=tuple, description="The annotations associated with the imported object")

    @field_validator("uid", mode="before")
    def validate_uid(cls, value: Any) -> Uid | None:
        if value is None:
            return None
        return Uid.from_string(value)


class AnnotationImportData(ImportData):
    class_name: str = Field(alias="class", description="The module and class of the annotation")

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
    )


class InstrumentImportData(ImportData, InstrumentSchema):
    pass


class TransactionImportData(ImportData, TransactionSchema):
    @field_validator("consideration", "fees", mode="plain")
    def validate_consideration(cls, value: Any) -> Any:
        if not isinstance(value, (str, float, int, Decimal, DecimalCurrency)):
            msg = "Consideration and fees must be a string or number"
            raise TypeError(msg)
        return value

    @override
    def get_schema_field_values(self, *, default_currency: Currency, **options) -> Mapping[str, Any]:  # pyright: ignore[reportIncompatibleMethodOverride]
        result = dict(self.iter_schema_field_values(**options))

        for field in ("consideration", "fees"):
            value = result.get(field)
            if value is not None and not isinstance(value, DecimalCurrency):
                result[field] = DecimalCurrency(value, default_currency=default_currency)

        return frozendict(result)


class LedgerImportData(ImportData):
    instrument: InstrumentImportData = Field(description="The instrument associated with the ledger")
    transactions: tuple[TransactionImportData, ...] = Field(default_factory=tuple, description="The transactions to import into the ledger")


class PortfolioImportData(ImportData):
    ledgers: tuple[LedgerImportData, ...] = Field(default_factory=tuple, description="The ledgers to import")


# MARK: Schema Importer Base Configuration
class SchemaImporterConfig(ImporterConfig, metaclass=ABCMeta):
    pass


# MARK: Schema Importer Base class
class SchemaImporter[C: SchemaImporterConfig](Importer[C], metaclass=ABCMeta):
    SKIP_SCHEMA_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "uid",
            "instance_name",
            "annotations",
            "version",
            "extra_dependency_uids",
        }
        | HierarchicalModel.INSTANCE_PARENT_FIELD_NAMES,
    )

    # TODO: What about UIDs? This will desync any incremental UID generators - and means newly created entities may collide with imported ones
    #       We ideally want to remap UIDs on import to new ones, so that the UIDs in the imported data are only used for linking within the imported data.
    def _import_annotations(self, entity: Entity, annotations_data: tuple[AnnotationImportData, ...], imported_annotations: dict[Uid, Annotation]) -> None:
        for annotation_data in annotations_data:
            # If the annotation was already imported, reuse it
            if annotation_data.uid is not None and (annotation := imported_annotations.get(annotation_data.uid)) is not None:
                # TODO: Validate data matches?
                entity.j.add(annotation)

            else:
                module_path, class_name = annotation_data.class_name.rsplit(".", 1)
                module = importlib.import_module(f".{module_path}", "app")
                klass = getattr(module, class_name)
                if klass is None:
                    msg = f"Annotation class '{annotation_data.class_name}' not found."
                    raise KeyError(msg)
                elif not issubclass(klass, Annotation):
                    msg = f"Class '{annotation_data.class_name}' is not a subclass of Annotation."
                    raise TypeError(msg)

                extra: frozendict[str, Any] = frozendict(typing_cast("dict[str, Any]", annotation_data.__pydantic_extra__))
                annotation = klass.create(entity, **extra)

                if annotation_data.uid is not None:
                    imported_annotations[annotation_data.uid] = annotation

    def _import_ledgers_from_schema(self, ledgers: tuple[LedgerImportData, ...]) -> None:
        imported_annotations: dict[Uid, Annotation] = {}

        for ledger_data in ledgers:
            instrument_data = ledger_data.instrument
            instrument = Instrument(**instrument_data.get_schema_field_values(skip=type(self).SKIP_SCHEMA_FIELDS))

            transactions = set()
            for transaction_data in ledger_data.transactions:
                transaction = Transaction(**transaction_data.get_schema_field_values(default_currency=instrument.currency, skip=type(self).SKIP_SCHEMA_FIELDS))
                transactions.add(transaction)

            ledger = Ledger(instrument=instrument, transactions=transactions)
            self.portfolio.j.ledgers.add(ledger)

            # Import annotations
            self._import_annotations(instrument, instrument_data.annotations, imported_annotations=imported_annotations)
            self._import_annotations(ledger, ledger_data.annotations, imported_annotations=imported_annotations)

            for transaction in ledger.transactions:
                for transaction_data in ledger_data.transactions:
                    if transaction_data.uid == transaction.uid:
                        break
                else:
                    continue
                self._import_annotations(transaction, transaction_data.annotations, imported_annotations=imported_annotations)

    def _import_portfolio_from_schema(self, portfolio_data: PortfolioImportData) -> None:
        self._import_ledgers_from_schema(portfolio_data.ledgers)
