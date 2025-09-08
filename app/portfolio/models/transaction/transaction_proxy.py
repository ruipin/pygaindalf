# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ...collections.uid_proxy import UidProxySequence, UidProxyOrderedViewSet, UidProxyOrderedViewFrozenSet

from .transaction import Transaction



class UidProxyTransactionSequence(UidProxySequence[Transaction]):
    pass


class UidProxyOrderedViewTransactionFrozenSet(UidProxyOrderedViewFrozenSet[Transaction, UidProxyTransactionSequence]):
    pass


class UidProxyOrderedViewTransactionSet(UidProxyOrderedViewTransactionFrozenSet, UidProxyOrderedViewSet[Transaction, UidProxyTransactionSequence]):
    pass