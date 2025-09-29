# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from string.templatelib import Interpolation
from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from string.templatelib import Template


# t-string to f-string conversion functions taken from https://peps.python.org/pep-0750/#example-implementing-f-strings-with-t-strings
def convert(value: object, conversion: Literal["a", "r", "s"] | None) -> object:
    if conversion == "a":
        return ascii(value)
    elif conversion == "r":
        return repr(value)
    elif conversion == "s":
        return str(value)
    return value


def tstring_as_fstring(template: Template) -> str:
    parts = []
    for item in template:
        match item:
            case str() as s:
                parts.append(s)
            case Interpolation(value, _, conversion, format_spec):
                value = convert(value, conversion)
                value = format(value, format_spec)
                parts.append(value)
    return "".join(parts)
