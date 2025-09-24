# SPDX-License-Identifier: GPLv3

import pytest

from .annotation_types import (
    HostEntity,
    SampleIncrementingAnnotation,
    SampleUniqueAnnotation,
)
from app.portfolio.models.annotation import Annotation


@pytest.mark.portfolio
@pytest.mark.annotation
class TestAnnotationBasic:
    def test_incrementing_annotation_basic_lifecycle(self):
        host = HostEntity()
        assert len(list(host.annotations)) == 0

        a1 = SampleIncrementingAnnotation.create(host, payload=1)
        a2 = SampleIncrementingAnnotation.create(host, payload=2)

        # Different UIDs, same namespace
        assert a1.uid != a2.uid
        assert a1.uid.namespace == SampleIncrementingAnnotation.uid_namespace()
        assert a2.uid.namespace == SampleIncrementingAnnotation.uid_namespace()

        # Parent tracks annotation uids and they are part of children set
        ann_uids = set(host.annotation_uids)
        assert a1.uid in ann_uids and a2.uid in ann_uids
        assert set(host.children_uids) >= ann_uids

        # Narrowing helpers
        assert Annotation.narrow_to_entity(a1.uid) is a1
        assert Annotation.narrow_to_entity(a2.uid) is a2

        # Deleting annotation updates parent's annotation set only; host not invalidated
        a1.delete()
        ann_uids_after = set(host.annotation_uids)
        assert a1.uid not in ann_uids_after
        assert a2.uid in ann_uids_after

        # Clean up
        a2.delete()
        assert len(list(host.annotation_uids)) == 0

    def test_unique_annotation_is_unique_per_parent(self):
        host = HostEntity()
        u1 = SampleUniqueAnnotation.create(host, payload=10)

        # Instance name and uid tie to parent
        assert u1.uid.namespace == SampleUniqueAnnotation.uid_namespace()
        assert str(host.uid) in u1.instance_name

        # Second creation for same parent should produce same UID and conflict in store
        with pytest.raises(ValueError):
            SampleUniqueAnnotation.create(host, payload=11)

        # Parent contains exactly one uid of this annotation type
        uids = list(host.get_annotation_uids(SampleUniqueAnnotation))
        assert uids == [u1.uid]

        # Delete and recreate should succeed again (since store entry removed on delete)
        u1.delete()
        u2 = SampleUniqueAnnotation.create(host, payload=12)
        assert u2.payload == 12
        assert list(host.get_annotation_uids(SampleUniqueAnnotation)) == [u2.uid]
