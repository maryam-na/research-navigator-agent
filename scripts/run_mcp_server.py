"""Run the local ResearchNavigator MCP server."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mcp_server import create_mcp_server


def main() -> int:
    create_mcp_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
