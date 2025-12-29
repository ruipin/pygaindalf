# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

"""Main entry point for the pygaindalf CLI application.

Initializes logging and configuration, parses CLI arguments, and executes commands.
"""

from pathlib import Path

from app.runtime import Runtime
from app.util.helpers.env_file import EnvFile


def main() -> None:
    # Load environment variables from 'env' file if it exists
    env_file = Path("env")
    if env_file.is_file():
        EnvFile(env_file).apply()

    # Initialize and run the application runtime
    runtime = Runtime()
    runtime.run()


if __name__ == "__main__":
    main()
