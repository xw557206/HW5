"""The agents' one and only route to shop data.

The backend holds no database connection. Every figure an agent uses — stock,
cash, invoices, rent — arrives through the MCP server defined in `.mcp.json`,
which is the single place SQL is written.

Keeping it that way matters: the business rules live inside the MCP tools, so
a backend that could read or write the database directly would be a way to
walk straight past them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic_ai.mcp import MCPToolset, StdioTransport

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".mcp.json"
SERVER_NAME = "campus-customs"


def _server_config() -> dict:
    """Read the launch command from .mcp.json rather than repeating it here."""
    if not CONFIG.exists():
        raise FileNotFoundError(
            f"{CONFIG} is missing. It defines how to launch the MCP server."
        )
    servers = json.loads(CONFIG.read_text(encoding="utf-8")).get("mcpServers", {})
    if SERVER_NAME not in servers:
        raise KeyError(
            f"'{SERVER_NAME}' is not in {CONFIG.name}. Found: {', '.join(servers) or 'nothing'}."
        )
    return servers[SERVER_NAME]


# Tools the dashboard may call but the agents may not. An agent able to
# approve its own request would make the approval rule decorative; an agent
# able to reset the database could erase the record of what it did.
HUMAN_ONLY_TOOLS = {"decide_approval", "reset_working_database"}


def build_toolset() -> MCPToolset:
    """The full toolset, including the human-only tools.

    Used by the API, which acts on a person's instruction. Agents get
    `agent_toolset()` instead.
    """
    cfg = _server_config()
    return MCPToolset(
        StdioTransport(
            command=cfg["command"],
            args=cfg["args"],
            # The server needs the project root importable and on its cwd.
            env={**os.environ, **cfg.get("env", {}), "PYTHONPATH": str(ROOT)},
            cwd=str(ROOT),
        ),
        id=SERVER_NAME,
        # Tool definitions do not change mid-run, so fetch them once.
        cache_tools=True,
    )


def agent_toolset(toolset: MCPToolset):
    """The same connection with the human-only tools filtered out.

    The agents never see these tools, so they cannot call them even if a
    prompt went wrong — the capability is absent rather than discouraged.
    """
    return toolset.filtered(lambda ctx, tool: tool.name not in HUMAN_ONLY_TOOLS)
