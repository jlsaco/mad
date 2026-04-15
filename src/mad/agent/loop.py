from __future__ import annotations

from mad.agent.tools import AGENT_TOOLS, execute_tool
from mad.core import log
from mad.core.sessions import SessionStore
from mad.providers import factory


async def run_agent_loop(
    store: SessionStore,
    session_id: str,
    session: dict,
    user_message: str,
) -> None:
    """Run the agent loop for one user message.

    Every event is appended to the session log (source of truth — hard rule 6)
    and pushed to the SSE queue so subscribers see it in real time.
    """
    store.emit_and_push(session_id, "session.status_running")
    session["status"] = "running"

    provider = factory.get_provider(session["agent"]["provider"])
    system = session["agent"].get("system", "")

    messages: list[dict] = []
    for event in log.get_events(session_id):
        if event["type"] == "user.message":
            messages.append({"role": "user", "content": event["content"]})
        elif event["type"] == "agent.message" and event.get("content"):
            messages.append({"role": "assistant", "content": event["content"]})

    if not messages or messages[-1] != {"role": "user", "content": user_message}:
        messages.append({"role": "user", "content": user_message})

    stop_reason = "end_turn"
    try:
        while True:
            response = await provider.complete(system=system, messages=messages, tools=AGENT_TOOLS)
            stop_reason = response.stop_reason

            if response.text:
                store.emit_and_push(session_id, "agent.message", {"content": response.text})
                messages.append({"role": "assistant", "content": response.text})

            if not response.tool_uses:
                break

            # Hard rule 1: only structured tool_use blocks are honored.
            tool_results = []
            for tu in response.tool_uses:
                store.emit_and_push(session_id, "agent.tool_use", {
                    "tool": tu.name,
                    "input": tu.input,
                    "tool_use_id": tu.id,
                })
                result = execute_tool(session_id, tu)
                store.emit_and_push(session_id, "agent.tool_result", {
                    "tool": tu.name,
                    "result": result,
                    "tool_use_id": tu.id,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

            if stop_reason != "tool_use":
                break

    except Exception as exc:
        store.emit_and_push(session_id, "session.error", {"error": str(exc)})
        stop_reason = "error"

    store.emit_and_push(session_id, "session.status_idle", {"stop_reason": stop_reason})
    session["status"] = "idle"

    q = store.sse_queues.get(session_id)
    if q is not None:
        await q.put(None)
