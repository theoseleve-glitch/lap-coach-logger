"""Entry point for ``python -m lap_coach_logger``."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lap-coach-logger",
        description="Local telemetry logger for sim racing",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug-level logging"
    )
    args = parser.parse_args()

    from lap_coach_logger.bootstrap import run

    run(debug_override=args.debug)


if __name__ == "__main__":
    main()
