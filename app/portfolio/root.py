# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import Field, field_validator, ConfigDict, InstanceOf, PrivateAttr, computed_field
from typing import Any, override

from requests import Session

from ..util.callguard import callguard_property

from ..util.mixins import LoggableHierarchicalModel

from .models.uid import Uid
from .models.store.entity_store import EntityStore
from .models.portfolio import Portfolio
from .journal.session_manager import SessionManager
from .journal.session import JournalSession



class PortfolioRoot(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True,
    )


    # MARK: Portfolio
    portfolio : InstanceOf[Portfolio] = Field(default_factory=Portfolio, description="The portfolio instance this manager is for.")

    @property
    def portfolio_uid(self) -> Uid:
        return self.portfolio.uid

    @portfolio_uid.setter
    def portfolio_uid(self, value : Uid) -> None:
        portfolio = Portfolio.by_uid(value)
        if portfolio is None:
            raise ValueError(f"No Portfolio found with uid {value}")
        self.portfolio = portfolio

    @override
    def __hash__(self) -> int:
        return hash((self.__class__.__name__, hash(self.portfolio_uid)))

    @field_validator('portfolio', mode='before')
    def _validate_portfolio(portfolio : Any) -> Portfolio:
        if not isinstance(portfolio, Portfolio):
            raise TypeError(f"Expected Portfolio, got {type(portfolio).__name__}")

        if portfolio.superseded:
            raise ValueError(f"EntityJournal.portfolio '{portfolio}' is superseded.")

        return portfolio


    # MARK: Session Manager
    session_manager : InstanceOf[SessionManager] = Field(default_factory=SessionManager, description="Session manager associated with this manager's portfolio")

    def on_session_start(self, session : JournalSession) -> None:
        pass

    def on_session_end(self, session : JournalSession) -> None:
        pass

    def on_session_commit(self, session : JournalSession) -> None:
        superseding = self.portfolio.superseding
        if superseding is None:
            raise ValueError("Cannot refresh entities: portfolio has no superseding portfolio.")

        if superseding is not self.portfolio:
            self.portfolio = superseding

        self.garbage_collect(who=session.actor, why=session.reason)

    def on_session_abort(self, session : JournalSession) -> None:
        pass


    # MARK: Entity Store
    entity_store : InstanceOf[EntityStore] = Field(default_factory=EntityStore.get_global_store, description="The entity store associated with this manager's portfolio.")

    def garbage_collect(self, who : str = 'system', why : str = 'garbage collect') -> None:
        self.entity_store.mark_and_sweep(self.portfolio_uid, who=who, why=why)
