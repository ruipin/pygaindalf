# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from contextvars import ContextVar
from functools import cached_property
from typing import TYPE_CHECKING, Self

from ..components.providers import ProviderType
from ..util.callguard import callguard_class
from ..util.helpers.decimal import DecimalFactory
from ..util.mixins import LoggableHierarchicalNamedMixin


if TYPE_CHECKING:
    from ..components.providers import Provider
    from ..components.providers.forex import ForexProvider
    from ..portfolio.journal import SessionManager
    from ..portfolio.models.portfolio import PortfolioProtocol
    from ..portfolio.models.transaction import Transaction
    from ..runtime import Runtime
    from .context_config import ContextConfig


CURRENT_CONTEXT: ContextVar[Context | None] = ContextVar("CURRENT_CONTEXT", default=None)


@callguard_class()
class Context(LoggableHierarchicalNamedMixin, metaclass=ABCMeta):
    _parent: Context | Runtime
    _config: ContextConfig

    def __init__(self, *, parent: Context | Runtime, config: ContextConfig) -> None:
        self._parent = parent
        self._config = config

    # MARK: Runtime
    @cached_property
    def _runtime(self) -> Runtime:
        from ..runtime import Runtime

        parent = self._parent
        if isinstance(parent, Runtime):
            return parent
        return parent._runtime  # noqa: SLF001

    # MARK: Configuration
    @cached_property
    def decimal(self) -> DecimalFactory:
        return DecimalFactory(self._config.decimal)

    # Portfolio
    # TODO: Apply access permissions:
    #   - block access when inside a provider entrypoint
    #   - RO access when inside an exporter or other component with explicitly defined readonly access
    @property
    @abstractmethod
    def portfolio(self) -> PortfolioProtocol:
        msg = "Subclasses must implement the 'portfolio' property."
        raise NotImplementedError(msg)

    @property
    def transactions(self) -> Iterable[Transaction]:
        for ledger in self.portfolio.ledgers:
            yield from ledger.transactions

    @property
    def session_manager(self) -> SessionManager:
        return self.portfolio.session_manager

    # MARK: Context Manager
    @staticmethod
    def get_current_or_none() -> Context | None:
        return CURRENT_CONTEXT.get()

    @staticmethod
    def get_current() -> Context:
        if (current := CURRENT_CONTEXT.get()) is None:
            msg = "No active Context found. Please ensure you are inside a component."
            raise RuntimeError(msg)
        return current

    def __enter__(self) -> Self:
        # Setup context variable
        self._ctx_token = CURRENT_CONTEXT.set(self)

        # Setup decimal context
        self._decimal_ctx = self.decimal.context_manager()
        self._decimal_ctx.__enter__()

        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        # Teardown decimal context
        if (decimal_ctx := getattr(self, "_decimal_ctx", None)) is not None:
            decimal_ctx.__exit__(_exc_type, _exc_value, _traceback)
            del self._decimal_ctx

        # Teardown context variable
        if (ctx_token := getattr(self, "_ctx_token", None)) is not None:
            CURRENT_CONTEXT.reset(ctx_token)
            del self._ctx_token

    # MARK: Providers
    def _remap_provider_key(self, key: ProviderType | str) -> str:
        return self._config.providers_remap.get(key, key)

    def has_provider(self, key: ProviderType | str) -> bool:
        key = self._remap_provider_key(key)
        return self._runtime.has_provider(key)

    def get_provider_or_none(self, key: ProviderType | str) -> Provider | None:
        key = self._remap_provider_key(key)
        return self._runtime.get_provider_or_none(key)

    def get_provider(self, key: ProviderType | str) -> Provider:
        key = self._remap_provider_key(key)
        return self._runtime.get_provider(key)

    def get_forex_provider(self, key: ProviderType | str = ProviderType.FOREX) -> ForexProvider:
        key = self._remap_provider_key(key)
        return self._runtime.get_forex_provider(key)
