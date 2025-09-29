# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging

import pytest

from app.util.logging.levels import LoggingLevel


@pytest.mark.logging
@pytest.mark.logging_levels
class TestLoggingLevel:
    @pytest.mark.parametrize(
        ("input", "expected"),
        [
            (10, 10),
            (logging.INFO, logging.INFO),
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("warning", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("critical", logging.CRITICAL),
            ("5", 5),
            ("20", 20),
            ("0", 0),
            ("-1", -1),
        ],
    )
    def test_accepts_int_and_str(self, input, expected):  # noqa: A002
        model = LoggingLevel(input)
        assert model.value == expected

    @pytest.mark.parametrize(
        "input",
        [
            "notalevel",
            3.14,
            None,
            [],
            {},
        ],
    )
    def test_rejects_invalid(self, input):  # noqa: A002
        with pytest.raises((ValueError, TypeError)):
            LoggingLevel(input)

    @pytest.mark.parametrize(
        ("input", "expected_name", "expected_repr"),
        [
            ("DEBUG", "DEBUG", "LoggingLevel.DEBUG"),
            (logging.INFO, "INFO", "LoggingLevel.INFO"),
            ("warning", "WARNING", "LoggingLevel.WARNING"),
            (42, "42", "LoggingLevel(42)"),
            (592, "592", "LoggingLevel(592)"),
            ("5", "5", "LoggingLevel(5)"),
            ("-1", "OFF", "LoggingLevel.OFF"),
        ],
    )
    def test_str_output(self, input, expected_name, expected_repr):  # noqa: A002
        model = LoggingLevel(input)
        assert model.name == expected_name
        assert str(model) == expected_name
        assert repr(model) == expected_repr
