# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from collections.abc import Mapping
from typing import TYPE_CHECKING

from frozendict import frozendict

from ..components.providers import Provider, ProviderType
from ..components.providers.forex import ForexProvider
from ..context import DirectContext
from ..portfolio.models.root import PortfolioRoot
from ..util.mixins import LoggableHierarchicalNamedMixin, ParentType


if TYPE_CHECKING:
    from ..config import ConfigManager


class Runtime(LoggableHierarchicalNamedMixin):
    initialized: bool

    config: ConfigManager
    portfolio_root: PortfolioRoot
    providers: Mapping[ProviderType | str, Provider]

    # MARK: Initialization
    def __init__(self, *, config: ConfigManager | None = None, instance_parent: ParentType | None = None, instance_name: str | None = None) -> None:
        super().__init__(instance_parent=instance_parent, instance_name=instance_name)

        self.initialized = False

        if config is None:
            from ..config import CFG

            config = CFG

        self.config = config

    def initialize(self) -> None:
        if self.initialized:
            return

        self._initialize_config()
        self._initialize_portfolio()
        self._initialize_providers()
        self._initialize_context()

        self.initialized = True

    def _initialize_config(self) -> None:
        self.config.initialize()

    def _initialize_portfolio(self) -> None:
        self.portfolio_root = root = PortfolioRoot()
        root.set_as_global_root()
        with root.session_manager(actor=self.instance_hierarchy, reason="Initialize portfolio root"):
            root.create_root_entity()

    def _initialize_providers(self) -> None:
        providers = {}
        for key, provider in self.config.providers.items():
            provider = provider.create_component(instance_parent=self)
            assert isinstance(provider, Provider)
            providers[key] = provider

        self.providers = frozendict(providers)

    def _initialize_context(self) -> None:
        self.context = DirectContext(parent=self, config=self.config.default.context)

    # MARK: Run
    def run(self) -> None:
        from .runtime_orchestrator import RuntimeOrchestrator, RuntimeOrchestratorConfig

        if not self.initialized:
            self.initialize()

        orchestrator_config = RuntimeOrchestratorConfig(package="app.runtime", components=self.config.agents)
        orchestrator = RuntimeOrchestrator(orchestrator_config, instance_name="orchestrator", instance_parent=self)
        with self.context as ctx:
            orchestrator.run(ctx)

    # MARK: Providers
    def has_provider(self, key: ProviderType | str) -> bool:
        return key in self.providers

    def get_provider_or_none(self, key: ProviderType | str) -> Provider | None:
        return self.providers.get(key)

    def get_provider(self, key: ProviderType | str) -> Provider:
        if provider := self.get_provider_or_none(key):
            return provider
        msg = f"Provider '{key}' not found in runtime providers: {list(self.providers.keys())}"
        raise KeyError(msg)

    def get_forex_provider(self, key: ProviderType | str = ProviderType.FOREX) -> ForexProvider:
        provider = self.get_provider(key)
        if not isinstance(provider, ForexProvider):
            msg = f"Expected ForexProvider for key '{key}', got {type(provider).__name__}"
            raise TypeError(msg)
        return provider
