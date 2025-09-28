# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from .iterable   import EntityProxyIterable
from .iterator   import EntityProxyIterator
from .collection import EntityProxyCollection, EntityProxyMutableCollection
from .sequence   import EntityProxySequence, EntityProxyMutableSequence
from .mapping    import EntityProxyMapping, EntityProxyMutableMapping
from .set        import *


__all__ = [
    "EntityProxyIterable"      ,
    "EntityProxyIterator"      ,
    "EntityProxyCollection"    , "EntityProxyMutableCollection"    ,
    "EntityProxySequence"      , "EntityProxyMutableSequence"      ,
    "EntityProxyMapping"       , "EntityProxyMutableMapping"       ,
    "EntityProxySet"           , "EntityProxyMutableSet"           ,
    "GenericEntityProxySet"    , "GenericEntityProxyMutableSet"    ,
    "EntityProxySet"           , "EntityProxyMutableSet"           ,
]