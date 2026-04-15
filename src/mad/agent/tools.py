from __future__ import annotations

import subprocess

from mad.core.workspace import workspace_path
from mad.providers.base import ToolUse

AGENT_TOOLS = [
    {
        "name": "bash",
        "description": "Execute a bash command in the workspace sandbox.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
]


def execute_tool(session_id: str, tool_use: ToolUse) -> str:
    """Execute a structured tool call in the session workspace."""
    workspace = workspace_path(session_id)
    if tool_use.name == "bash":
        command = tool_use.input.get("command", "")
        result = subprocess.run(
            command, shell=True, cwd=str(workspace),
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout + (("\n" + result.stderr) if result.stderr else "")
    if tool_use.name == "read_file":
        path = workspace / tool_use.input.get("path", "").lstrip("/")
        try:
            return path.read_text()
        except Exception as exc:
            return f"error: {exc}"
    if tool_use.name == "write_file":
        path = workspace / tool_use.input.get("path", "").lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tool_use.input.get("content", ""))
        return "ok"
    return f"unknown tool: {tool_use.name}"
