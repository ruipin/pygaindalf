# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from __future__ import annotations

import datetime

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from iso4217 import Currency

from app.components.agents.importers.importer.schema import SchemaImporter
from app.portfolio.models.annotation.forex import ForexAnnotation
from app.portfolio.models.entity import Entity
from app.portfolio.models.transaction import Transaction
from app.util.helpers.decimal_currency import DecimalCurrency


def validate_entity(entity: Entity, data: Mapping[str, Any]) -> None:
    record = entity.record_or_none
    assert record is not None, f"Entity of type {type(entity).__name__} has no record to validate against"
    schema_values = record.get_schema_field_values(skip=SchemaImporter.SKIP_SCHEMA_FIELDS)

    # Ensure there are no extra keys in the input data
    data_keys = set(data.keys())
    schema_keys = set(schema_values.keys())
    assert data_keys.issubset(schema_keys), f"Data keys {data_keys} do not match schema keys {schema_keys}"

    # Drive validation from the schema so we always cover all fields
    for field_name, actual_value in schema_values.items():
        expected_value = data.get(field_name, None)
        if expected_value is None:
            field_info = type(record).model_fields.get(field_name)
            assert field_info is not None, f"Field info for '{field_name}' not found in entity of type {type(entity).__name__}"
            assert not field_info.is_required(), f"Missing required field '{field_name}' in data for entity of type {type(entity).__name__}"
            expected_value = field_info.get_default(call_default_factory=True, validated_data=entity.__dict__)

        if isinstance(actual_value, Entity):
            assert isinstance(expected_value, Mapping)
            validate_entity(actual_value, expected_value)
        elif isinstance(actual_value, Iterable) and not isinstance(actual_value, (str, bytes, bytearray)):
            assert isinstance(expected_value, Sequence)
            validate_entities(actual_value, expected_value)
        else:
            if isinstance(actual_value, Currency):
                actual_value = actual_value.code
            elif isinstance(actual_value, DecimalCurrency):
                assert isinstance(entity, Transaction)
                expected_value = DecimalCurrency(expected_value, default_currency=entity.instrument.currency)
            elif isinstance(actual_value, Decimal):
                expected_value = Decimal(expected_value)
            elif isinstance(actual_value, datetime.date):
                expected_value = datetime.date.fromisoformat(expected_value)

            if type(actual_value) is not type(expected_value):
                try:
                    type(actual_value)(expected_value)  # pyright: ignore[reportArgumentType, reportCallIssue]
                except (TypeError, ValueError) as err:
                    msg = f"Type mismatch on field '{field_name}': expected type {type(actual_value).__name__}, got type {type(expected_value).__name__}"
                    raise AssertionError(msg) from err

            assert actual_value == expected_value, f"Mismatch on field '{field_name}': expected {expected_value}, got {actual_value}"


def validate_entities(entities: Iterable[Entity], data_list: Sequence[Mapping[str, Any]]) -> None:
    for entity, data in zip(entities, data_list, strict=True):
        validate_entity(entity, data)


def validate_portfolio(runtime_instance, ledgers_data: list[dict[str, Any]]) -> None:
    portfolio = runtime_instance.context.portfolio

    ledgers = list(portfolio)
    validate_entities(ledgers, ledgers_data)


def validate_forex_annotations(
    runtime_instance,
    ledgers_data: Sequence[dict[str, Any]],
    currencies: Iterable[str] = ("GBP", "USD", "JPY"),
) -> None:
    validate_portfolio(runtime_instance, list(ledgers_data))

    portfolio = runtime_instance.context.portfolio
    forex_provider = runtime_instance.context.get_forex_provider()

    requested_currencies = tuple(currencies)

    for ledger in portfolio:
        for txn in ledger:
            ann = ForexAnnotation.get(txn)
            assert ann is not None

            for cur_str in requested_currencies:
                cur = Currency(cur_str)
                if cur == txn.currency:
                    assert cur not in ann.exchange_rates
                    assert cur not in ann.considerations
                    assert ann.get_exchange_rate(cur) == Decimal(1)
                    assert ann.get_consideration(cur) == txn.consideration
                else:
                    rate = ann.get_exchange_rate(cur)
                    consideration = ann.get_consideration(cur)

                    assert rate is not None
                    assert consideration is not None

                    expected_rate = forex_provider.get_daily_rate(
                        source=txn.currency,
                        target=cur,
                        date=txn.date,
                    )

                    assert rate == expected_rate
                    assert consideration == DecimalCurrency(
                        expected_rate * txn.consideration,
                        currency=consideration.currency,
                    )

                    assert ann.get_consideration(cur) == consideration
