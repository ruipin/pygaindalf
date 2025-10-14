# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Protocol


if TYPE_CHECKING:
    from ...collections import OrderedViewSet
    from ...journal import Session, SessionManager
    from ...util import Uid
    from ..instrument import Instrument, InstrumentRecord
    from ..ledger import Ledger
    from .portfolio_journal import PortfolioJournal


class PortfolioProtocol(Protocol):
    # MARK: Metadata
    @property
    def instance_name(self) -> str: ...
    @property
    def uid(self) -> Uid: ...
    @property
    def version(self) -> int: ...

    # MARK: Session management
    @property
    def session_manager(self) -> SessionManager: ...
    @property
    def session(self) -> Session: ...
    @property
    def journal(self) -> PortfolioJournal: ...
    @property
    def j(self) -> PortfolioJournal: ...

    # MARK: Ledgers
    @property
    def ledgers(self) -> OrderedViewSet[Ledger]: ...
    def __getitem__(self, index: int | Uid | InstrumentRecord | Instrument) -> Ledger: ...
    def __contains__(self, value: object) -> bool: ...
    def __iter__(self) -> Iterator[Ledger]: ...
    def __len__(self) -> int: ...

    # MARK: Dumping
    def model_dump(self, *args, **kwargs) -> dict[str, Any]: ...
