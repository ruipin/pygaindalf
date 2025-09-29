# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable


def _ensure_mro_order(final: type, target: type, others: type | Iterable[type], *, before: bool = True, fail: bool = True) -> bool:
    mro = final.__mro__
    index = mro.index(target)

    if isinstance(others, type):
        others = (others,)

    for cur in others:
        try:
            cur_index = mro.index(cur)
            if (cur_index < index) if before else (cur_index > index):
                if fail:
                    msg = f"'{target.__name__}' must come *{'before' if before else 'after'}* '{cur.__name__}' in the '{type(final).__name__}' MRO"
                    raise TypeError(msg)
                return False
        except ValueError:
            continue  # If the class is not in the MRO, we ignore it

    return True


def ensure_mro_order(
    final: type | object, target: type, *, before: type | Iterable[type] | None = None, after: type | Iterable[type] | None = None, fail: bool = True
) -> bool:
    if not isinstance(final, type):
        final = type(final)

    if before is not None:
        if not _ensure_mro_order(final, target, before, before=True, fail=fail):
            return False

    if after is not None:
        if not _ensure_mro_order(final, target, after, before=False, fail=fail):
            return False

    return True
