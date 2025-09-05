# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from ...collections.uid_proxy import UidProxySequence, UidProxyOrderedViewSet

from .ledger import Ledger



class UidProxyLedgerSequence(UidProxySequence[Ledger]):
    pass


class UidProxyOrderedViewLedgerSet(UidProxyOrderedViewSet[Ledger, UidProxyLedgerSequence]):
    pass