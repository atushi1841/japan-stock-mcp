"""stdio エントリポイント — MCPBバンドル（ローカル実行）用。

Claude Desktop / Cursor / Smithery のローカル配布（MCPB）として起動するときの入り口。
transport は FastMCP 既定の stdio（stdout は JSON-RPC 専用、ログは stderr）。
"""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import server  # noqa: E402  (server.py は FastMCP インスタンス mcp を定義する)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    server.mcp.run()  # FastMCP 既定 transport = stdio


if __name__ == "__main__":
    main()