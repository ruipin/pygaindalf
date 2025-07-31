# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Main entry point for the pygaindalf CLI application.
Initializes logging and configuration, parses CLI arguments, and executes commands.
"""

import sys
from app.util.args import ARGS
from app.util.config.parser import ConfigFileParser
from app.util.logging import getLogger

if __name__ == "__main__":
    config_parser = ConfigFileParser(getattr(ARGS, 'configfile'))

    log1 = getLogger('1')
    log1.info("log1")
    log2 = getLogger('2')
    log2.warning("log2")
    log3 = getLogger('3', parent=log2)
    log3.error("log3")
    log3.info("yay")

    log1.debug('Cmdline= %s', ' '.join(sys.argv))
    #CFG.debug()