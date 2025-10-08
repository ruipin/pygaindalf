# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import warnings

from .entity import Entity, EntityImpl, EntityLog, EntityRecord, EntitySchema, EntitySchemaBase
from .root import EntityRoot, PortfolioRoot
from .store import EntityStore, StringUidMapping


__all__ = [
    "Entity",
    "EntityImpl",
    "EntityLog",
    "EntityRecord",
    "EntityRoot",
    "EntitySchema",
    "EntitySchemaBase",
    "EntityStore",
    "PortfolioRoot",
    "StringUidMapping",
]


# Filter out specific warnings during normal operation
warnings.filterwarnings("ignore", module="app.util.helpers.generics", message=r"get_journal_class.*EntityRecordBase\.T_Journal.*Journal", category=UserWarning)
warnings.filterwarnings("ignore", module="app.util.helpers.generics", message=r"ForwardRef.*Journal.*not implemented", category=UserWarning)
