# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro


from pathlib import Path
from typing import TYPE_CHECKING, override

from rich.console import Console, ConsoleRenderable, RenderableType
from rich.containers import Renderables
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text


if TYPE_CHECKING:
    import logging

    from rich.traceback import Traceback


class CustomRichHandler(RichHandler):
    @override
    def __init__(
        self,
        *args,
        rich_tracebacks: bool = True,
        show_path: bool = True,
        show_level: bool = True,
        level_width: int = 1,
        level_color_everything: bool = True,
        level_prefix: str = "[",
        level_suffix: str = "] ",
        show_name: bool = True,
        enable_link_path: bool = False,
        **kwargs,
    ) -> None:
        console = Console(stderr=True)

        super().__init__(*args, console=console, rich_tracebacks=rich_tracebacks, enable_link_path=enable_link_path, **kwargs)

        self.show_path = show_path
        self.show_level = show_level
        self.level_width = level_width
        self.level_color_everything = level_color_everything
        self.show_name = show_name
        self.level_prefix = level_prefix
        self.level_suffix = level_suffix

    def should_format(self, record: logging.LogRecord) -> bool:
        simple = getattr(record, "simple", False)
        return not simple

    def get_level(self, record: logging.LogRecord) -> str:
        name = record.levelname
        return name[0].ljust(self.level_width)

    def get_level_style(self, record: logging.LogRecord) -> str:
        return f"logging.level.{record.levelname.lower()}"

    def get_message_style(self, record: logging.LogRecord) -> str:
        if self.level_color_everything:
            return self.get_level_style(record)
        else:
            return "log.message"

    @override
    def render_message(self, record: logging.LogRecord, message: str) -> ConsoleRenderable:
        """Render message text in to Text.

        Args:
            record (LogRecord): logging Record.
            message (str): String containing log message.

        Returns:
            ConsoleRenderable: Renderable to display log message.

        """
        text = Text()

        if self.should_format(record):
            if self.show_level or self.show_name:
                text.append(self.level_prefix, style="dim")

            if self.show_level:
                text.append(self.get_level(record), style=self.get_level_style(record))

            if self.show_name:
                text.append(f"{':' if self.show_level else ''}{record.name}", style="dim")

            if self.show_level or self.show_name:
                text.append(self.level_suffix, style="dim")

        text.append(message)

        return text

    @override
    def render(self, *args, record: logging.LogRecord, message_renderable: ConsoleRenderable, traceback: Traceback | None, **kwargs) -> ConsoleRenderable:
        if not self.should_format(record):
            return message_renderable

        path = Path(record.pathname).name
        line_no = record.lineno
        link_path = record.pathname if self.enable_link_path else None

        renderables = [message_renderable]
        if traceback:
            renderables.append(traceback)

        # Setup table
        output = Table.grid(padding=(0, 1))
        output.expand = True
        output.add_column(ratio=1, style=self.get_message_style(record), overflow="fold")
        if self.show_path and path:
            output.add_column(style="log.path")

        # Setup row contents
        row: list[RenderableType] = []
        row.append(Renderables(renderables))
        if self.show_path and path:
            path_text = Text()
            path_text.append(path, style=f"link file://{link_path}" if link_path else "")
            if line_no:
                path_text.append(":")
                path_text.append(
                    f"{line_no}",
                    style=f"link file://{link_path}#{line_no}" if link_path else "",
                )
            row.append(path_text)
        output.add_row(*row)

        # Done
        return output
