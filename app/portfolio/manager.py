# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from pydantic import Field, field_validator, ConfigDict, InstanceOf
from typing import Any, override

from requests import Session

from ..util.mixins import LoggableHierarchicalModel

from .models.uid import Uid
from .portfolio import Portfolio
from .journal.session_manager import SessionManager


class PortfolioManager(LoggableHierarchicalModel):
    model_config = ConfigDict(
        extra='forbid',
        frozen=False,
        validate_assignment=True,
    )

    # MARK: Entity
    portfolio : InstanceOf[Portfolio] = Field(default_factory=Portfolio, description="The portfolio instance this manager is for.")

    @property
    def portfolio_uid(self) -> Uid:
        return self.portfolio.uid

    @property
    def version(self) -> int:
        return self.portfolio.version

    @override
    def __hash__(self) -> int:
        return hash((self.__class__.__name__, hash(self.portfolio)))

    @field_validator('portfolio', mode='before')
    def _validate_portfolio(portfolio : Any) -> Portfolio:
        if not isinstance(portfolio, Portfolio):
            raise TypeError(f"Expected Portfolio, got {type(portfolio).__name__}")

        if portfolio.superseded:
            raise ValueError(f"EntityJournal.portfolio '{portfolio}' is superseded.")

        return portfolio

    def refresh_entities(self) -> None:
        superseding = self.portfolio.superseding
        if superseding is None:
            raise ValueError("Cannot refresh entities: portfolio has no superseding portfolio.")
        if superseding is not self.portfolio:
            self.portfolio = superseding


    # MARK: Session Manager
    session_manager : InstanceOf[SessionManager] = Field(default_factory=SessionManager, description="Session manager associated with this manager's portfolio")