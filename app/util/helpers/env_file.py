# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import os

from pathlib import Path


class EnvFile:
    def __init__(self, filepath: Path | str) -> None:
        self.filepath = Path(filepath)
        self.values = {}
        self._load()

    def _load(self) -> None:
        if not self.filepath.exists():
            msg = f"Environment file '{self.filepath}' does not exist."
            raise FileNotFoundError(msg)

        with self.filepath.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                split = line.split("=", 1)
                if len(split) != 2:  # noqa: PLR2004
                    msg = f"Invalid line in environment file '{self.filepath}': {line}"
                    raise ValueError(msg)

                key = split[0].strip()
                value = split[1].strip()
                self.values[key] = value

    def apply(self) -> None:
        for key, value in self.values.items():
            os.environ[key] = value
