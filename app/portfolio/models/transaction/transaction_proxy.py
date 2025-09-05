# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ...collections.uid_proxy import UidProxySequence, UidProxyOrderedViewSet

from .transaction import Transaction



class UidProxyTransactionSequence(UidProxySequence[Transaction]):
    pass


class UidProxyOrderedViewTransactionSet(UidProxyOrderedViewSet[Transaction, UidProxyTransactionSequence]):
    pass