from __future__ import annotations

import signal
import sys

from .command_registry import build_parser, dispatch_command
from .runtime import RuntimeContext


def _install_default_sigpipe() -> None:
    # Restore default SIGPIPE so commands piped into `head`/`less` exit quietly
    # instead of surfacing a Python BrokenPipeError traceback. Unix-only;
    # Windows has no SIGPIPE.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def main(argv: list[str] | None = None):
    _install_default_sigpipe()
    ctx = RuntimeContext()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch_command(args, ctx)
    except BrokenPipeError:
        # Output pipe closed before we finished writing. Swallow cleanly —
        # any remaining stderr writes should also be suppressed so the
        # caller's `| head` doesn't print tracebacks on exit.
        try:
            sys.stderr.close()
        except Exception:
            pass
        return 0
