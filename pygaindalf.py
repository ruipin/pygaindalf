# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Main entry point for the pygaindalf CLI application.
Initializes logging and configuration, parses CLI arguments, and executes commands.
"""

import sys
from app.config import CFG
from app.logging import getLogger

def main():
    CFG.initialize()

    log1 = getLogger('1')
    log1.info("log1")
    log2 = getLogger('2')
    log2.warning("log2")
    log3 = getLogger('3', parent=log2)
    log3.error("log3")
    log3.info("log3 info")
    log2.debug("log2 debug")

    cls = CFG.providers['oanda'].component_class
    cls(CFG.providers['oanda'])

if __name__ == "__main__":
    main()