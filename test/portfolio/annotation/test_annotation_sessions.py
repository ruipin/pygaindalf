# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

from typing import TYPE_CHECKING

import pytest

from .annotation_types import HostEntity, SampleIncrementingAnnotation, SampleUniqueAnnotation


if TYPE_CHECKING:
    from app.portfolio.journal.session_manager import SessionManager
    from app.portfolio.models.root import EntityRoot


@pytest.mark.portfolio
@pytest.mark.session
@pytest.mark.annotation
class TestAnnotationSessions:
    def test_incrementing_annotations_with_session(self, entity_root: EntityRoot, session_manager: SessionManager):
        # Create host entity inside a session attached to the root
        with session_manager(actor="tester", reason="create-host"):
            host = entity_root.root = HostEntity()

        # Create annotations in another session; adding annotations should not require parent invalidation
        with session_manager(actor="tester", reason="add-annotations") as s:
            a1 = SampleIncrementingAnnotation.create(host, payload=1)
            a2 = SampleIncrementingAnnotation.create(host, payload=2)
            assert a1 is not a2
            assert s.dirty is True
            assert host.dirty is True

        # After commit, annotations exist on the same entity instance
        assert host.dirty is False
        assert len(host.annotation_uids) == 2
        assert a1.uid in host.annotation_uids and a2.uid in host.annotation_uids
        assert a1.uid in host.children_uids and a2.uid in host.children_uids

        # Remove one annotation in a new session
        with session_manager(actor="tester", reason="remove-annotation") as s:
            assert a1.superseded is False
            a1.delete()

            assert a1.marked_for_deletion is True
            assert a2.marked_for_deletion is False
            assert a1.dirty is True
            assert host.dirty is True
            assert s.dirty is True
        assert a1.deleted is True
        assert a2.deleted is False

        # Exactly one annotation remains
        anns = list(host.get_annotations(SampleIncrementingAnnotation))
        assert len(anns) == 1

    def test_unique_annotation_with_session(self, entity_root: EntityRoot, session_manager: SessionManager):
        with session_manager(actor="tester", reason="create-host"):
            host = entity_root.root = HostEntity()

        # Create unique annotation; parent is tracked as dirty during the session
        with session_manager(actor="tester", reason="unique-add") as s:
            u = SampleUniqueAnnotation.create(host, payload=5)
            assert host.dirty is True
            assert s.dirty is True
        assert host.dirty is False

        # Creating another unique annotation for same parent should fail
        with session_manager(actor="tester", reason="unique-dup"), pytest.raises(ValueError, match=r"Entity with UID .* already exists."):
            SampleUniqueAnnotation.create(host, payload=6)

        # Delete and recreate succeeds
        with session_manager(actor="tester", reason="unique-recreate") as s:
            u.delete()
            s.commit()
            assert u.exists is False

            u2 = SampleUniqueAnnotation.create(host, payload=7)
            assert u2 is u
            assert u2.payload == 7

        assert u2.exists
        assert u2 is u
