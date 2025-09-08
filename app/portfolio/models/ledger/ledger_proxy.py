# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ...collections.uid_proxy import UidProxySequence, UidProxyOrderedViewSet, UidProxyOrderedViewFrozenSet

from .ledger import Ledger



class UidProxyLedgerSequence(UidProxySequence[Ledger]):
    pass


class UidProxyOrderedViewLedgerFrozenSet(UidProxyOrderedViewFrozenSet[Ledger, UidProxyLedgerSequence]):
    pass


class UidProxyOrderedViewLedgerSet(UidProxyOrderedViewLedgerFrozenSet, UidProxyOrderedViewSet[Ledger, UidProxyLedgerSequence]):
    pass