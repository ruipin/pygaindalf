# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import pytest
from datetime import datetime

from app.portfolio.journal.session import Session
from app.portfolio.portfolio import Portfolio


@pytest.mark.journal
@pytest.mark.session
class TestSessionBasics:
    def test_session_initialization_no_edits_commit_noop(self):
        s = Session(actor="tester", reason="unit test")
        assert s.actor == "tester"
        assert s.reason == "unit test"
        assert isinstance(s.start_time, datetime)
        assert s.ended is False
        assert s.has_uncommited_edits is False
        assert len(s) == 0

        # Commit on empty session should be a no-op
        s.commit()
        assert s.has_uncommited_edits is False

    @pytest.mark.xfail(raises=NotImplementedError, reason="Session commit not implemented yet for sessions with edits")
    def test_add_entity_journal_via_get(self):
        p = Portfolio()
        with p.session_manager(actor="tester", reason="add journal") as s:
            assert s.has_uncommited_edits is False
            assert len(s) == 0

            # Accessing the portfolio's journal should create an entity journal for it
            j = p.journal
            assert j.entity is p
            assert s.has_uncommited_edits is True
            assert len(s) == 1

            # Access again returns same journal (no duplication)
            j2 = p.journal
            assert j2 is j
            assert len(s) == 1

        # Exiting context with edits currently attempts a commit that is NotImplemented.
        # Because we created edits above, the context manager exit should currently raise.
        # Therefore this test focuses only on the inside-of-context assertions.

    @pytest.mark.xfail(raises=NotImplementedError, reason="Session commit not implemented yet for sessions with edits")
    def test_commit_with_edits_raises_not_implemented(self):
        p = Portfolio()
        with p.session_manager(actor="tester", reason="commit edits") as s:
            _ = p.journal  # create an edit (entity journal)
            assert s.has_uncommited_edits is True
            # Explicit commit should raise NotImplementedError because implementation pending
            s.commit()

    def test_abort_clears_edits_without_ending_session(self):
        p = Portfolio()
        with p.session_manager(actor="tester", reason="abort edits") as s:
            _ = p.journal  # create entity journal
            assert s.has_uncommited_edits is True
            assert len(s) == 1

            s.abort()

            assert s.has_uncommited_edits is False
            assert len(s) == 0
            # Current abort() implementation does not mark session ended
            assert s.ended is False

            # Abort when already cleared should be a no-op
            s.abort()
            assert s.has_uncommited_edits is False

    def test_end_without_edits(self):
        s = Session(actor="tester", reason="end no edits")
        assert s.has_uncommited_edits is False
        s.end()  # should not raise
        assert s.ended is True

        with pytest.raises(RuntimeError):
            s.end()

    @pytest.mark.xfail(raises=NotImplementedError, reason="Session commit inside end() not implemented when edits pending")
    def test_end_with_edits_triggers_commit(self):
        p = Portfolio()

        with p.session_manager(actor="tester", reason="end with edits") as s:
            _ = p.journal  # create edits
            assert s.has_uncommited_edits is True
            # end() should attempt commit and therefore raise NotImplementedError currently
            s.end()

