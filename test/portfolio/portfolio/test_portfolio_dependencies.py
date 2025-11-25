# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import datetime
import re

from decimal import Decimal
from typing import Any, NamedTuple, override

import pytest

from iso4217 import Currency

from app.portfolio.models.entity import EntityRecord
from app.portfolio.models.entity.dependency_event_handler import EntityDependencyEventType
from app.portfolio.models.entity.dependency_event_handler.impl import EntityDependencyEventHandlerImpl
from app.portfolio.models.entity.dependency_event_handler.model import EntityDependencyEventHandlerModel
from app.portfolio.models.instrument import Instrument, InstrumentRecord
from app.portfolio.models.instrument.instrument_type import InstrumentType
from app.portfolio.models.ledger import Ledger, LedgerRecord
from app.portfolio.models.portfolio.portfolio import Portfolio
from app.portfolio.models.root.portfolio_root import PortfolioRoot
from app.portfolio.models.transaction import Transaction, TransactionRecord, TransactionType
from app.util.helpers.decimal_currency import DecimalCurrency
from app.util.models.uid import Uid


class DepEventCall(NamedTuple):
    event: EntityDependencyEventType
    self_uid: Uid
    entity_uid: Uid
    matched_attributes: frozenset[str] | None


@pytest.mark.portfolio
@pytest.mark.dependencies
class TestPortfolioDependencies:
    def _seed_portfolio_with_ledger_and_transactions(self, portfolio_root: PortfolioRoot) -> tuple[Portfolio, Instrument, Ledger, Transaction, Transaction]:
        """Create an Instrument, two Transactions, and a Ledger linked to the instrument; add it to the Portfolio via a session."""
        with portfolio_root.session_manager(actor="seed", reason="seed graph"):
            inst_appl = Instrument(ticker="AAPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
            tx_buy = Transaction(
                type=TransactionType.BUY,
                date=datetime.date(2025, 1, 1),
                quantity=Decimal(10),
                consideration=DecimalCurrency(1500, currency="USD"),
            )
            tx_sell = Transaction(
                type=TransactionType.SELL,
                date=datetime.date(2025, 1, 5),
                quantity=Decimal(4),
                consideration=DecimalCurrency(620, currency="USD"),
            )
            ledg_appl = Ledger(instrument=inst_appl, transactions={tx_buy, tx_sell})
            portfolio_root.portfolio.journal.ledgers.add(ledg_appl)

        portfolio = portfolio_root.portfolio

        return portfolio, inst_appl, ledg_appl, tx_buy, tx_sell

    def test_children_and_dependents(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio with AAPL instrument, one ledger, and two transactions
        portfolio, inst_appl, ledg_appl, tx_buy, tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        # Assert: children of portfolio include the ledger
        assert ledg_appl.uid in portfolio.children_uids
        assert ledg_appl.uid in {child.uid for child in portfolio.children}

        # Assert: children of ledger include instrument and transactions
        cuids = set(ledg_appl.children_uids)
        assert inst_appl.uid in cuids
        assert {tx_buy.uid, tx_sell.uid}.issubset(cuids)
        child_uids = {child.uid for child in ledg_appl.children}
        assert inst_appl.uid in child_uids
        assert {tx_buy.uid, tx_sell.uid}.issubset(child_uids)

        # Assert: dependents — transactions list their parent ledger as a dependent via parent->child relationship
        # (ledger deletion should notify transactions which then self-delete)
        # Note: Transactions may not expose ledger as instance_parent for other APIs, but dependents graph includes parent entity
        # through EntityDependents.dependent_uids.
        for tx in (tx_buy, tx_sell):
            assert ledg_appl.uid in {dep.uid for dep in tx.dependents}

        # Assert: extra_dependencies default to none
        assert ledg_appl.extra_dependency_uids == frozenset()
        assert list(ledg_appl.extra_dependencies) == []

        # Assert: EntityRecord-level extra_dependencies is immutable (no add method on the proxy)
        assert not hasattr(ledg_appl.extra_dependencies, "add")

    def test_extra_dependencies_add_remove_and_dependents_update(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio with baseline AAPL ledger
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)

        # Arrange: create another instrument (MSFT) and attach to portfolio in the same session to avoid GC
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_msft = Instrument(ticker="MSFT", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_msft = Ledger(instrument=inst_msft)
            portfolio_root.portfolio.journal.ledgers.add(ledg_msft)

        # Act: add extra dependency via the journal (entity field is immutable)
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="add extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_msft)

        # Assert: persisted extra dependency and reverse dependents tracking
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding
        assert inst_msft.uid in ledg_appl.extra_dependency_uids
        # The depended-upon entity (inst_b) should list the ledger as a dependent
        assert ledg_appl.uid in {dep.uid for dep in inst_msft.dependents}

        # Act+Assert: attempting to delete while still attached should raise
        with (
            pytest.raises(Exception, match=r"Entity record <IR MSFT v1> is a child of <LR MSFT v1> and therefore the latter cannot be deleted."),
            portfolio_root.session_manager(actor="tester", reason="delete extra dep (should fail)", exit_on_exception=False),
        ):
            inst_msft.delete()

        # Assert: state unchanged after failed delete
        assert inst_msft.deleted is False
        assert inst_msft.marked_for_deletion is False
        assert inst_msft.superseded is False

        # Act: detach MSFT's ledger from portfolio, then delete successfully
        ledg_appl_record_before_detach = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="detach inst_b ledger"):
            p = portfolio_root.portfolio
            ledg_msft_attached = p[inst_msft]
            assert ledg_msft_attached in p.ledgers
            p.journal.ledgers.discard(ledg_msft_attached)
            assert ledg_msft_attached not in p.journal.ledgers
            inst_msft.delete()

        # Assert: after commit, the ledger no longer lists MSFT as an extra dependency
        assert ledg_appl_record_before_detach.superseded
        assert ledg_appl.record is ledg_appl_record_before_detach.superseding
        assert inst_msft.uid not in ledg_appl.extra_dependency_uids

    def test_dependency_event_handlers_updated_and_deleted(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)

        # Arrange: create NVDA instrument and attach to portfolio (parent dependency)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_nvda = Instrument(ticker="NVDA", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_nvda = Ledger(instrument=inst_nvda)
            portfolio_root.portfolio.journal.ledgers.add(ledg_nvda)
        inst_nvda_uid = inst_nvda.uid

        # Arrange: attach NVDA as an extra dependency of AAPL's ledger
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_nvda)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        # Arrange: register dependency event handlers on LedgerRecord
        # Capture (event, self_ledger_uid, entity_uid, matched_attributes) # noqa: ERA001
        calls: list[DepEventCall] = []

        def entity_matcher(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            # Only react to inst_b
            return record.uid == inst_nvda_uid

        def attr_matcher(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            # Match currency updates only
            return attribute == "currency"

        def handler(
            owner: LedgerRecord,
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            calls.append(DepEventCall(event=event, self_uid=owner.uid, entity_uid=record.uid, matched_attributes=matched_attributes))

        # Register on LedgerRecord so only Ledgers receive these callbacks
        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler,
            on_updated=True,
            on_deleted=True,
            entity_matchers=entity_matcher,
            attribute_matchers=attr_matcher,
        ).register(LedgerRecord)

        # Act: trigger UPDATED by editing inst_nvda.currency inside a session (and committing)
        inst_nvda_record = inst_nvda.record
        with portfolio_root.session_manager(actor="tester", reason="update inst_b"):
            jb = inst_nvda.journal

            # Edit mutable field that doesn't affect instance naming
            jb.currency = Currency("EUR")

        # Assert: received two UPDATED callbacks (parent ledger + extra dependency ledger) with matched {currency}
        assert inst_nvda_record.superseded
        assert inst_nvda.record is inst_nvda_record.superseding
        # Expect two UPDATED callbacks: one for the parent ledger of inst_nvda, and one for ledg_appl (extra dependency)
        update_calls = [c for c in calls if c.event == EntityDependencyEventType.UPDATED]
        assert len(update_calls) == 2
        # The self ledgers should be the current ledger for inst_nvda and ledg_appl
        ledg_nvda_current = portfolio_root.portfolio[inst_nvda]
        assert {c.self_uid for c in update_calls} == {ledg_nvda_current.uid, ledg_appl.uid}
        # EntityRecord uid should match inst_nvda and matched attributes should be {currency}
        assert all(c.entity_uid == inst_nvda.uid for c in update_calls)
        assert all(c.matched_attributes == frozenset({"currency"}) for c in update_calls)

        # Prep: clear for next phase
        calls.clear()

        # Act+Assert: Trigger DELETED — first ensure deletion while attached raises
        with (
            pytest.raises(Exception, match=r"Entity record <IR NVDA v2> is a child of <LR NVDA v1> and therefore the latter cannot be deleted."),
            portfolio_root.session_manager(actor="tester", reason="delete inst_b (should fail)", exit_on_exception=False),
        ):
            inst_nvda.delete()

        # Assert: state unchanged after failed delete
        assert inst_nvda.superseded is False
        assert inst_nvda.deleted is False
        assert inst_nvda.marked_for_deletion is False

        # Act: detach its ledger and then delete successfully (GC will remove entity)
        ledg_appl_record_before_detach = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="delete inst_nvda"):
            ledg_nvda_attached = portfolio_root.portfolio[inst_nvda]
            portfolio_root.portfolio.journal.ledgers.discard(ledg_nvda_attached)

        # Assert: deleted by garbage collection
        assert inst_nvda.superseded is True
        assert inst_nvda.deleted is True
        assert inst_nvda.record_or_none is None
        with pytest.raises(ValueError, match=re.escape(r"Entity <I NVDA v3 (D)> has been deleted and does not have a record.")):
            _ = inst_nvda.record

        # Assert: after commit, we should have DELETED callback(s) and extra dep removed
        deleted_calls = [c for c in calls if c.event == EntityDependencyEventType.DELETED]
        assert deleted_calls and all(c.entity_uid == inst_nvda.uid and c.matched_attributes is None for c in deleted_calls)
        assert ledg_appl_record_before_detach.superseded
        assert ledg_appl.record is ledg_appl_record_before_detach.superseding
        assert inst_nvda.uid not in ledg_appl.extra_dependency_uids

    def test_event_handlers_multiple_entity_and_attribute_matchers(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)

        # Arrange: create ISIN-instrument and attach to portfolio (ticker-independent identity)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_isin_0001 = Instrument(isin="US0000000001", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_isin_0001 = Ledger(instrument=inst_isin_0001)
            portfolio_root.portfolio.journal.ledgers.add(ledg_isin_0001)

        # Arrange: attach as extra dependency to receive events
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_isin_0001)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        # Prep: collection to capture handler calls
        calls: list[tuple[EntityDependencyEventType, str, frozenset[str] | None]] = []

        # Two entity matchers (OR). First one matches nothing; second matches inst_b
        def entity_matcher_noop(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            return False

        def entity_matcher_target(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            return record.uid == inst_isin_0001.uid

        # Two attribute matchers (OR). Match currency and ticker
        def attr_match_currency(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            return attribute == "currency"

        def attr_match_ticker(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            return attribute == "ticker"

        def handler(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            calls.append((event, str(record.uid), matched_attributes))

        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler,
            on_updated=True,
            on_deleted=True,
            entity_matchers=(entity_matcher_noop, entity_matcher_target),
            attribute_matchers=(attr_match_currency, attr_match_ticker),
        ).register(LedgerRecord)

        # Act: update by changing both currency and ticker in one session
        inst_isin_0001_record = inst_isin_0001.record
        with portfolio_root.session_manager(actor="tester", reason="update with multiple attrs"):
            jb = inst_isin_0001.journal
            jb.currency = Currency("EUR")
            jb.ticker = "FOO"
        assert inst_isin_0001_record.superseded
        assert inst_isin_0001.record is inst_isin_0001_record.superseding

        # Assert: a single UPDATED call capturing both attributes
        assert any(
            evt == EntityDependencyEventType.UPDATED and uid == str(inst_isin_0001.uid) and matched is not None and matched.issuperset({"currency", "ticker"})
            for (evt, uid, matched) in calls
        )

        # Prep: clear for deletion phase
        calls.clear()

        # Act+Assert: deletion while attached should raise
        with (
            pytest.raises(
                Exception, match=r"Entity record <IR US0000000001 v2> is a child of <LR US0000000001 v1> and therefore the latter cannot be deleted."
            ),
            portfolio_root.session_manager(actor="tester", reason="delete inst_b (should fail)", exit_on_exception=False),
        ):
            inst_isin_0001.delete()

        # Assert: state unchanged after failed delete
        assert inst_isin_0001.deleted is False
        assert inst_isin_0001.marked_for_deletion is False
        assert inst_isin_0001.superseded is False

        # Act: detach its ledger, then delete
        with portfolio_root.session_manager(actor="tester", reason="delete inst_b"):
            ledg_isin_0001_attached = portfolio_root.portfolio[inst_isin_0001]
            portfolio_root.portfolio.journal.ledgers.discard(ledg_isin_0001_attached)
            inst_isin_0001.delete()

        # Assert: deleted callback observed
        assert any(evt == EntityDependencyEventType.DELETED and uid == str(inst_isin_0001.uid) and matched is None for (evt, uid, matched) in calls)

    def test_event_handlers_none_matchers_match_all(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_goog = Instrument(ticker="GOOG", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_goog = Ledger(instrument=inst_goog)
            portfolio_root.portfolio.journal.ledgers.add(ledg_goog)

        # Arrange: attach as extra dependency
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_goog)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        # Prep: collection to capture handler calls
        calls: list[tuple[EntityDependencyEventType, str, frozenset[str] | None]] = []

        def handler(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            calls.append((event, str(record.uid), matched_attributes))

        # No entity or attribute filters: should fire for any dependent entity and any attribute
        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler,
            on_updated=True,
            on_deleted=True,
            entity_matchers=None,
            attribute_matchers=None,
        ).register(LedgerRecord)

        # Act: update by changing currency (no attribute filters => matched None)
        inst_goog_record = inst_goog.record
        with portfolio_root.session_manager(actor="tester", reason="update inst_b"):
            inst_goog.journal.currency = Currency("GBP")
        assert inst_goog_record.superseded
        assert inst_goog.record is inst_goog_record.superseding

        # Assert: UPDATED fired with matched None
        assert any(evt == EntityDependencyEventType.UPDATED and uid == str(inst_goog.uid) and matched is None for (evt, uid, matched) in calls)

        # Prep: clear for deletion phase
        calls.clear()

        # Act+Assert: delete should also fire with matched None; first attempt should fail while attached
        with (
            pytest.raises(Exception, match=r"Entity record <IR GOOG v2> is a child of <LR GOOG v1> and therefore the latter cannot be deleted."),
            portfolio_root.session_manager(actor="tester", reason="delete inst_b (should fail)", exit_on_exception=False),
        ):
            inst_goog.delete()

        # Assert: state unchanged after failed delete
        assert inst_goog.deleted is False
        assert inst_goog.marked_for_deletion is False
        assert inst_goog.superseded is False

        # Act: detach and then delete
        with portfolio_root.session_manager(actor="tester", reason="delete inst_b"):
            ledg_goog_attached = portfolio_root.portfolio[inst_goog]
            portfolio_root.portfolio.journal.ledgers.discard(ledg_goog_attached)
            inst_goog.delete()

        # Assert: DELETED fired with matched None
        assert any(evt == EntityDependencyEventType.DELETED and uid == str(inst_goog.uid) and matched is None for (evt, uid, matched) in calls)

    def test_records_only_on_updated_or_only_on_deleted(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_amzn = Instrument(ticker="AMZN", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_amzn = Ledger(instrument=inst_amzn)
            portfolio_root.portfolio.journal.ledgers.add(ledg_amzn)

        # Arrange: attach AMZN as extra dependency
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_amzn)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        # Prep: capture full details as NamedTuple using Uid types
        update_calls: list[DepEventCall] = []
        del_calls: list[DepEventCall] = []

        def update_handler(
            owner: LedgerRecord,
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            update_calls.append(DepEventCall(event=event, self_uid=owner.uid, entity_uid=record.uid, matched_attributes=matched_attributes))

        def del_handler(
            owner: LedgerRecord,
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            del_calls.append(DepEventCall(event=event, self_uid=owner.uid, entity_uid=record.uid, matched_attributes=matched_attributes))

        def match_amzn(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            return record.uid == inst_amzn.uid

        def match_currency(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            return attribute == "currency"

        original_handler_count = len(LedgerRecord.__entity_dependency_event_handler_records__)

        # Register: record that only fires on updated
        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=update_handler,
            on_updated=True,
            on_deleted=False,
            entity_matchers=match_amzn,
            attribute_matchers=match_currency,
        ).register(LedgerRecord)

        # Register: record that only fires on deleted
        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=del_handler,
            on_updated=False,
            on_deleted=True,
            entity_matchers=match_amzn,
            attribute_matchers=None,
        ).register(LedgerRecord)

        assert len(LedgerRecord.__entity_dependency_event_handler_records__) == original_handler_count + 2
        assert len(list(LedgerRecord.iter_dependency_event_handlers())) == len(LedgerRecord.__entity_dependency_event_handler_records__)

        # Act: update should only trigger update_handler; expect two calls (parent ledger + extra dependency ledger)
        inst_amzn_record = inst_amzn.record
        with portfolio_root.session_manager(actor="tester", reason="update inst_b"):
            inst_amzn.journal.currency = Currency("JPY")
        assert inst_amzn_record.superseded
        assert inst_amzn.record is inst_amzn_record.superseding

        # Assert: collect current ledgers that depend on inst_amzn and validate calls
        ledg_amzn_current = portfolio_root.portfolio[inst_amzn]
        assert len(update_calls) == 2
        assert {c.event for c in update_calls} == {EntityDependencyEventType.UPDATED}
        assert {c.self_uid for c in update_calls} == {ledg_amzn_current.uid, ledg_appl.uid}
        assert all(c.entity_uid == inst_amzn.uid for c in update_calls)
        assert all(c.matched_attributes == frozenset({"currency"}) for c in update_calls)
        assert del_calls == []

        # Act+Assert: delete should only trigger del_handler; first attempt should fail while attached
        with (
            pytest.raises(Exception, match=r"Entity record <IR AMZN v2> is a child of <LR AMZN v1> and therefore the latter cannot be deleted."),
            portfolio_root.session_manager(actor="tester", reason="delete inst_b (should fail)", exit_on_exception=False),
        ):
            inst_amzn.delete()
        # State should be unchanged
        assert inst_amzn.deleted is False
        assert inst_amzn.marked_for_deletion is False
        assert inst_amzn.superseded is False

        # Act: detach AMZN's ledger
        ledg_appl_record_before_detach = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="detach inst_b ledger"):
            ledg_amzn_attached = portfolio_root.portfolio[inst_amzn]
            portfolio_root.portfolio.journal.ledgers.discard(ledg_amzn_attached)
        # Confirm AMZN was deleted by GC
        assert inst_amzn.superseded is True
        assert inst_amzn.deleted is True
        assert inst_amzn.record_or_none is None
        with pytest.raises(ValueError, match=re.escape(r"Entity <I AMZN v3 (D)> has been deleted and does not have a record.")):
            _ = inst_amzn.record

        # Assert: one or two delete calls (depending on whether both ledgers receive deletion callbacks)
        assert {c.event for c in del_calls} == {EntityDependencyEventType.DELETED}
        assert all(c.entity_uid == inst_amzn.uid and c.matched_attributes is None for c in del_calls)
        assert len(del_calls) >= 1
        assert ledg_appl_record_before_detach.superseded
        assert ledg_appl.record is ledg_appl_record_before_detach.superseding

    def test_dependency_event_handler_impl_updated_and_deleted(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio and create IMPL instrument with its own ledger
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_impl"):
            inst_impl = Instrument(ticker="IMPL", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_impl = Ledger(instrument=inst_impl)
            portfolio_root.portfolio.journal.ledgers.add(ledg_impl)

        target_uid = inst_impl.uid
        calls: list[DepEventCall] = []

        class LedgerDependencyHandler(EntityDependencyEventHandlerImpl[LedgerRecord, InstrumentRecord]):
            on_updated = True
            on_deleted = True

            @staticmethod
            @override
            def entity_matchers(owner: LedgerRecord, record: InstrumentRecord) -> bool:
                return record.uid == target_uid

            @staticmethod
            @override
            def attribute_matchers(owner: LedgerRecord, record: InstrumentRecord, attribute: str, value: Any) -> bool:
                return attribute in {"currency"}

            @staticmethod
            @override
            def handler(
                owner: LedgerRecord,
                event: EntityDependencyEventType,
                record: InstrumentRecord,
                *,
                matched_attributes: frozenset[str] | None = None,
            ) -> None:
                calls.append(DepEventCall(event=event, self_uid=owner.uid, entity_uid=record.uid, matched_attributes=matched_attributes))

        LedgerDependencyHandler().register(LedgerRecord)

        # Attach IMPL as an extra dependency of the AAPL ledger to observe multiple owners
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach impl extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_impl)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        # Act: update IMPL instrument by changing currency and ticker
        inst_impl_record = inst_impl.record
        with portfolio_root.session_manager(actor="tester", reason="update inst_impl"):
            jb = inst_impl.journal
            jb.currency = Currency("JPY")
        assert inst_impl_record.superseded
        assert inst_impl.record is inst_impl_record.superseding

        update_calls = [c for c in calls if c.event == EntityDependencyEventType.UPDATED]
        assert len(update_calls) == 2
        ledg_impl_current = portfolio_root.portfolio[inst_impl]
        assert {c.self_uid for c in update_calls} == {ledg_impl_current.uid, ledg_appl.uid}
        assert all(c.entity_uid == inst_impl.uid for c in update_calls)
        assert all(c.matched_attributes == frozenset({"currency"}) for c in update_calls)

        # Act+Assert: deletion while attached should fail and produce no handler invocations
        calls.clear()
        inst_impl_instance_name = inst_impl.instance_name
        with (
            pytest.raises(
                Exception,
                match=re.escape(
                    f"Entity record <IR {inst_impl_instance_name} v2> is a child of <LR {inst_impl_instance_name} v1> and therefore the latter cannot be deleted."
                ),
            ),
            portfolio_root.session_manager(actor="tester", reason="delete inst_impl (should fail)", exit_on_exception=False),
        ):
            inst_impl.delete()

        assert inst_impl.superseded is False
        assert inst_impl.deleted is False
        assert inst_impl.marked_for_deletion is False

        # Act: detach ledger and delete successfully
        ledg_impl_current_uid = portfolio_root.portfolio[inst_impl].uid
        ledg_appl_record_before_detach = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="detach inst_impl"):
            ledg_impl_attached = portfolio_root.portfolio[inst_impl]
            portfolio_root.portfolio.journal.ledgers.discard(ledg_impl_attached)
            inst_impl.delete()

        assert inst_impl.superseded is True
        assert inst_impl.deleted is True
        assert inst_impl.record_or_none is None
        with pytest.raises(
            ValueError,
            match=re.escape(f"Entity <I {inst_impl.instance_name} v3 (D)> has been deleted and does not have a record."),
        ):
            _ = inst_impl.record

        deleted_calls = [c for c in calls if c.event == EntityDependencyEventType.DELETED]
        assert deleted_calls
        assert {c.entity_uid for c in deleted_calls} == {inst_impl.uid}
        assert all(c.matched_attributes is None for c in deleted_calls)
        assert {c.self_uid for c in deleted_calls}.issubset({ledg_impl_current_uid, ledg_appl.uid})

        assert ledg_appl_record_before_detach.superseded
        assert ledg_appl.record is ledg_appl_record_before_detach.superseding
        assert inst_impl.uid not in ledg_appl.extra_dependency_uids

    def test_dependency_event_handler_record_generic_filtering_and_union(self, portfolio_root: PortfolioRoot):
        # Arrange: seed baseline portfolio with instrument and transactions
        _portfolio, inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)

        # Arrange: create a ledger whose transaction will become a non-instrument dependency of ledg_appl
        with portfolio_root.session_manager(actor="tester", reason="create non-instrument dependency"):
            inst_dep = Instrument(ticker="NFLX", type=InstrumentType.EQUITY, currency=Currency("USD"))
            tx_dep = Transaction(
                type=TransactionType.SELL,
                date=datetime.date(2025, 2, 1),
                quantity=Decimal(1),
                consideration=DecimalCurrency(100, currency="USD"),
            )
            ledg_dep = Ledger(instrument=inst_dep, transactions={tx_dep})
            portfolio_root.portfolio.journal.ledgers.add(ledg_dep)

        with portfolio_root.session_manager(actor="tester", reason="attach non-instrument dependency"):
            ledg_appl.journal.extra_dependencies.add(tx_dep)

        inst_calls: list[tuple[Uid, EntityDependencyEventType, type[EntityRecord], frozenset[str] | None]] = []
        union_calls: list[tuple[Uid, EntityDependencyEventType, type[EntityRecord], frozenset[str] | None]] = []

        def instrument_only_handler(
            owner: LedgerRecord,
            event: EntityDependencyEventType,
            record: InstrumentRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            inst_calls.append((owner.uid, event, type(record), matched_attributes))

        def union_handler(
            owner: LedgerRecord,
            event: EntityDependencyEventType,
            record: InstrumentRecord | TransactionRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            union_calls.append((owner.uid, event, type(record), matched_attributes))

        EntityDependencyEventHandlerModel[LedgerRecord, InstrumentRecord](
            handler=instrument_only_handler,
            on_updated=True,
            on_deleted=False,
            entity_matchers=None,
            attribute_matchers=None,
        ).register(LedgerRecord)

        EntityDependencyEventHandlerModel[LedgerRecord, InstrumentRecord | TransactionRecord](
            handler=union_handler,
            on_updated=True,
            on_deleted=False,
            entity_matchers=None,
            attribute_matchers=None,
        ).register(LedgerRecord)

        # Act: update instrument -> should notify both handlers
        inst_appl_record = inst_appl.record
        with portfolio_root.session_manager(actor="tester", reason="update instrument (generics filter)"):
            inst_appl.journal.currency = Currency("EUR")
        assert inst_appl_record.superseded
        assert inst_appl.record is inst_appl_record.superseding

        assert inst_calls, "Instrument-specific handler should receive instrument updates"
        assert {owner_uid for owner_uid, _event, record_cls, _matched in inst_calls} == {ledg_appl.uid}
        assert all(record_cls is InstrumentRecord for _owner_uid, _event, record_cls, _matched in inst_calls)

        assert union_calls, "Union handler should receive instrument updates"
        assert any(record_cls is InstrumentRecord for _owner_uid, _event, record_cls, _matched in union_calls)

        instrument_calls_count = len(inst_calls)
        union_calls_before_transaction = len(union_calls)

        # Act: update non-instrument dependency -> only union handler should match due to record generics
        tx_dep_record = tx_dep.record
        with portfolio_root.session_manager(actor="tester", reason="update transaction dependency (generics filter)"):
            tx_dep.journal.consideration = tx_dep.journal.consideration + Decimal(5)
        assert tx_dep_record.superseded
        assert tx_dep.record is tx_dep_record.superseding

        assert len(inst_calls) == instrument_calls_count, "Instrument-only handler should ignore non-instrument dependencies"

        assert len(union_calls) > union_calls_before_transaction
        union_transaction_calls = union_calls[union_calls_before_transaction:]
        assert all(event == EntityDependencyEventType.UPDATED for _owner_uid, event, _record_cls, _matched in union_transaction_calls)
        assert {owner_uid for owner_uid, _event, _record_cls, _matched in union_transaction_calls} == {ledg_dep.uid, ledg_appl.uid}
        assert all(record_cls is TransactionRecord for _owner_uid, _event, record_cls, _matched in union_transaction_calls)

    def test_multiple_records_same_class_with_distinct_attribute_filters(self, portfolio_root: PortfolioRoot):
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_isin_1111 = Instrument(isin="US1111111111", ticker=None, type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_isin_1111 = Ledger(instrument=inst_isin_1111)
            portfolio_root.portfolio.journal.ledgers.add(ledg_isin_1111)

        # Arrange: attach as extra dependency
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_isin_1111)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        target_uid = inst_isin_1111.uid
        calls_currency: list[frozenset[str] | None] = []
        calls_ticker: list[frozenset[str] | None] = []

        def entity_match(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            return record.uid == target_uid

        def match_currency(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            return attribute == "currency"

        def match_ticker(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            return attribute == "ticker"

        def handler_currency(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            if event == EntityDependencyEventType.UPDATED and record.uid == target_uid:
                calls_currency.append(matched_attributes)

        def handler_ticker(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            if event == EntityDependencyEventType.UPDATED and record.uid == target_uid:
                calls_ticker.append(matched_attributes)

        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler_currency,
            on_updated=True,
            on_deleted=False,
            entity_matchers=entity_match,
            attribute_matchers=match_currency,
        ).register(LedgerRecord)

        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler_ticker,
            on_updated=True,
            on_deleted=False,
            entity_matchers=entity_match,
            attribute_matchers=match_ticker,
        ).register(LedgerRecord)

        # Act: change both attributes in a single session
        inst_isin_1111_record = inst_isin_1111.record
        with portfolio_root.session_manager(actor="tester", reason="update both attrs"):
            jb = inst_isin_1111.journal
            jb.currency = Currency("CHF")
            jb.ticker = "BAR"
        assert inst_isin_1111_record.superseded
        assert inst_isin_1111.record is inst_isin_1111_record.superseding
        target_uid = inst_isin_1111.uid

        # Assert: each handler called once, capturing only its own matched attribute
        assert calls_currency and calls_currency[0] == frozenset({"currency"})
        assert calls_ticker and calls_ticker[0] == frozenset({"ticker"})

    def test_attribute_matchers_string_and_sequence(self, portfolio_root: PortfolioRoot):
        # Set up a graph with a ledger depending on an instrument that has an ISIN so ticker changes won't alter instance name
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_isin_2222 = Instrument(isin="US2222222222", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_isin_2222 = Ledger(instrument=inst_isin_2222)
            portfolio_root.portfolio.journal.ledgers.add(ledg_isin_2222)

        # Arrange: attach as extra dependency
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_isin_2222)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        target_uid = inst_isin_2222.uid
        calls: list[tuple[EntityDependencyEventType, frozenset[str] | None]] = []

        def entity_match(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            return record.uid == target_uid

        def handler_str(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            if record.uid == target_uid:
                calls.append((event, matched_attributes))

        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler_str,
            on_updated=True,
            on_deleted=False,
            entity_matchers=entity_match,
            attribute_matchers="currency",
        ).register(LedgerRecord)

        # Case 1 — Act: change currency
        inst_isin_2222_record = inst_isin_2222.record
        with portfolio_root.session_manager(actor="tester", reason="change currency"):
            inst_isin_2222.journal.currency = Currency("EUR")
        assert inst_isin_2222_record.superseded
        assert inst_isin_2222.record is inst_isin_2222_record.superseding
        target_uid = inst_isin_2222.uid

        # Case 1 — Assert: matched_attributes == {"currency"}
        assert any(evt == EntityDependencyEventType.UPDATED and matched == frozenset({"currency"}) for evt, matched in calls)

        # Case 1 — Negative: changing ticker should NOT trigger (filter is "currency")
        calls.clear()
        inst_isin_2222_record = inst_isin_2222.record
        with portfolio_root.session_manager(actor="tester", reason="change ticker"):
            inst_isin_2222.journal.ticker = "FOO"
        assert inst_isin_2222_record.superseded
        assert inst_isin_2222.record is inst_isin_2222_record.superseding
        target_uid = inst_isin_2222.uid
        assert calls == []

        # Case 2 — Arrange: attribute_matchers as a sequence of strings ("currency", "ticker")
        calls_seq: list[frozenset[str] | None] = []

        def handler_seq(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            if event == EntityDependencyEventType.UPDATED and record.uid == target_uid:
                calls_seq.append(matched_attributes)

        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler_seq,
            on_updated=True,
            on_deleted=False,
            entity_matchers=entity_match,
            attribute_matchers=("currency", "ticker"),
        ).register(LedgerRecord)

        # Case 2 — Act: change both in a single session
        inst_isin_2222_record = inst_isin_2222.record
        with portfolio_root.session_manager(actor="tester", reason="change both"):
            jb = inst_isin_2222.journal
            jb.currency = Currency("CHF")
            jb.ticker = "BAR"
        assert inst_isin_2222_record.superseded
        assert inst_isin_2222.record is inst_isin_2222_record.superseding
        target_uid = inst_isin_2222.uid

        # Case 2 — Assert: matched set includes both attributes
        assert calls_seq and calls_seq[0] is not None and calls_seq[0].issuperset({"currency", "ticker"})

    def test_attribute_matchers_mixed_string_and_callable(self, portfolio_root: PortfolioRoot):
        # Mixed: string matcher and callable matcher combined in one record
        # Arrange: seed portfolio
        _portfolio, _inst_appl, ledg_appl, _tx_buy, _tx_sell = self._seed_portfolio_with_ledger_and_transactions(portfolio_root)
        with portfolio_root.session_manager(actor="tester", reason="create+attach inst_b"):
            inst_isin_3333 = Instrument(isin="US3333333333", type=InstrumentType.EQUITY, currency=Currency("USD"))
            ledg_isin_3333 = Ledger(instrument=inst_isin_3333)
            portfolio_root.portfolio.journal.ledgers.add(ledg_isin_3333)

        # Arrange: attach as extra dependency
        ledg_appl_record_before_extra = ledg_appl.record
        with portfolio_root.session_manager(actor="tester", reason="attach extra dep"):
            ledg_appl.journal.extra_dependencies.add(inst_isin_3333)
        assert ledg_appl_record_before_extra.superseded
        assert ledg_appl.record is ledg_appl_record_before_extra.superseding

        target_uid = inst_isin_3333.uid
        calls: list[frozenset[str] | None] = []

        def entity_match(owner: LedgerRecord, record: EntityRecord) -> bool:  # noqa: ARG001
            return record.uid == target_uid

        def match_ticker(owner: LedgerRecord, record: EntityRecord, attribute: str, value: Any) -> bool:  # noqa: ARG001
            return attribute == "ticker"

        def handler(
            owner: LedgerRecord,  # noqa: ARG001
            event: EntityDependencyEventType,
            record: EntityRecord,
            *,
            matched_attributes: frozenset[str] | None = None,
        ) -> None:
            if event == EntityDependencyEventType.UPDATED and record.uid == target_uid:
                calls.append(matched_attributes)

        EntityDependencyEventHandlerModel[LedgerRecord, EntityRecord](
            handler=handler,
            on_updated=True,
            on_deleted=False,
            entity_matchers=entity_match,
            attribute_matchers=("currency", match_ticker),
        ).register(LedgerRecord)

        # Act: change currency only -> matches {"currency"}
        inst_isin_3333_record = inst_isin_3333.record
        with portfolio_root.session_manager(actor="tester", reason="currency only"):
            inst_isin_3333.journal.currency = Currency("EUR")
        assert inst_isin_3333_record.superseded
        assert inst_isin_3333.record is inst_isin_3333_record.superseding
        target_uid = inst_isin_3333.uid
        assert calls and calls[-1] == frozenset({"currency"})

        # Act: change ticker only -> matches {"ticker"}
        calls.clear()
        inst_isin_3333_record = inst_isin_3333.record
        with portfolio_root.session_manager(actor="tester", reason="ticker only"):
            inst_isin_3333.journal.ticker = "FOO"
        assert inst_isin_3333_record.superseded
        assert inst_isin_3333.record is inst_isin_3333_record.superseding
        target_uid = inst_isin_3333.uid
        assert calls and calls[-1] == frozenset({"ticker"})

        # Act: change both in same session -> matches both
        calls.clear()
        inst_isin_3333_record = inst_isin_3333.record
        with portfolio_root.session_manager(actor="tester", reason="both attrs"):
            jb = inst_isin_3333.journal
            jb.currency = Currency("CHF")
            jb.ticker = "BAR"
        assert inst_isin_3333_record.superseded
        assert inst_isin_3333.record is inst_isin_3333_record.superseding
        target_uid = inst_isin_3333.uid
        assert calls and calls[-1] is not None and calls[-1].issuperset({"currency", "ticker"})
