# SPDX-License-Identifier: GPLv3

import pytest

from .annotation_types import (
    HostEntity,
    SampleIncrementingAnnotation,
    SampleUniqueAnnotation,
)
from app.portfolio.models.root import EntityRoot
from app.portfolio.journal.session_manager import SessionManager


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

        # After commit, annotations exist
        host = host.superseding
        assert len(host.annotation_uids) == 2
        assert a1.uid in host.annotation_uids and a2.uid in host.annotation_uids
        assert a1.uid in host.children_uids and a2.uid in host.children_uids

        # Remove one annotation in a new session
        with session_manager(actor="tester", reason="remove-annotation") as s:
            assert a1.superseded is False
            a1.delete()

            assert a1.marked_for_deletion is True
            assert a2.marked_for_deletion is False
            assert host.dirty is True
            assert s.dirty is True
        assert a1.deleted is True
        assert a2.deleted is False

        # Exactly one annotation remains
        host = host.superseding
        anns = list(host.get_annotations(SampleIncrementingAnnotation))
        assert len(anns) == 1

    def test_unique_annotation_with_session(self, entity_root: EntityRoot, session_manager: SessionManager):
        with session_manager(actor="tester", reason="create-host"):
            host = entity_root.root = HostEntity()

        # Create unique annotation; parent remains clean
        with session_manager(actor="tester", reason="unique-add") as s:
            u = SampleUniqueAnnotation.create(host, payload=5)
            assert host.dirty is True
            assert s.dirty is True
        host = host.superseding

        # Creating another unique annotation for same parent should fail
        with session_manager(actor="tester", reason="unique-dup"):
            with pytest.raises(ValueError):
                SampleUniqueAnnotation.create(host, payload=6)

        # Delete and recreate succeeds
        with session_manager(actor="tester", reason="unique-recreate") as s:
            u.delete()
            s.commit()
            host = host.superseding
            u2 = SampleUniqueAnnotation.create(host, payload=7)
            assert u2.payload == 7
