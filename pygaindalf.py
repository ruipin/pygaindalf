# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Main entry point for the pygaindalf CLI application.

Initializes logging and configuration, parses CLI arguments, and executes commands.
"""

from app.runtime import Runtime


def main() -> None:
    runtime = Runtime()
    runtime.run()


if __name__ == "__main__":
    main()
