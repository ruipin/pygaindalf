# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""
Argument parsing and CLI option definitions for pygaindalf
Defines global options, command actions, and wraps argparse for use throughout the application.
"""

from .parser import ArgsParser
from ..config.path import ConfigFilePath

PARSER = ArgsParser()

# Logging
PARSER.add('config.logging.levels.file', '-lv', '--log-verbosity', action='store', help='Logfile verbosity. Can be numeric or one of the default logging levels (CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10)')
PARSER.add('config.logging.levels.tty' , '-v', '--verbosity', action='store', help='Console verbosity. Can be numeric or one of the default logging levels (CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10)')

# Configuration
PARSER.add('configfile', '-c', '--config', type=ConfigFilePath, action='store', required=True, help='Configuration file to load')

# Parse
PARSER.parse()
ARGS = PARSER.namespace