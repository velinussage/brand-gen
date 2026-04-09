from __future__ import annotations

from .command_registry import build_parser, dispatch_command
from .runtime import RuntimeContext


def main(argv: list[str] | None = None):
    ctx = RuntimeContext()
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch_command(args, ctx)
