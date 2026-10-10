"""Append-only audit trail at output/audit_trail.json.

Every agent run appends one record. Earlier records are never deleted or
rewritten, so the file is a growing history of what the team did rather than
a snapshot of the last run.

Steps are reconstructed from the messages PydanticAI returns rather than
logged inside each tool, which keeps the tools clean and still captures calls
the tools never saw — a malformed call the model had to retry, for instance.

Deliberately not recorded:

* **No secrets.** No API key, no environment values.
* **No private reasoning.** Thinking content is skipped; only a boolean notes
  that the model produced some. An audit trail records actions taken, not
  hidden chain-of-thought.
* **No unbounded blobs.** Arguments and results are clipped.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = ROOT / "output" / "audit_trail.json"

MAX_ARG_CHARS = 220
MAX_RESULT_CHARS = 320
MAX_TEXT_CHARS = 400

# Agent runs can overlap, so read-modify-write is made atomic.
_lock = threading.Lock()
logger = logging.getLogger("campus_customs.audit")


def now_iso() -> str:
    """Real wall-clock UTC — when the run happened, not the shop's date."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def _clip(value: Any, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str, ensure_ascii=False)
        except Exception:
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def steps_from_messages(messages: list[Any]) -> tuple[list[dict[str, Any]], bool]:
    """Turn a run's messages into one step per tool call.

    Returns the steps plus whether any reasoning parts appeared (noted as a
    flag only; the content is never read).
    """
    calls: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []
    thinking = False
    iteration = 0

    for message in messages:
        for part in getattr(message, "parts", []):
            kind = getattr(part, "part_kind", "")

            if kind == "thinking":
                thinking = True
                continue

            if kind == "tool-call":
                tool_name = getattr(part, "tool_name", "unknown")
                # `final_result` is how PydanticAI delivers structured output.
                # It is the stop step, not a shop action, so it is labelled
                # separately and left out of the iteration count.
                is_final = tool_name == "final_result"
                if not is_final:
                    iteration += 1
                try:
                    args = part.args_as_dict()
                except Exception:
                    args = getattr(part, "args", None)
                step = {
                    "iteration": None if is_final else iteration,
                    "action": "final_output" if is_final else "tool_call",
                    "tool_name": tool_name,
                    "tool_args": _clip(args, MAX_ARG_CHARS),
                    "result_summary": None,
                    "status": "pending",
                }
                steps.append(step)
                call_id = getattr(part, "tool_call_id", None)
                if call_id:
                    calls[call_id] = step

            elif kind == "tool-return":
                step = calls.get(getattr(part, "tool_call_id", None))
                if step is None:
                    continue
                step["result_summary"] = _clip(getattr(part, "content", None), MAX_RESULT_CHARS)
                step["status"] = "ok"
                ts = getattr(part, "timestamp", None)
                if ts is not None:
                    step["at"] = ts.isoformat(timespec="seconds")

            elif kind == "retry-prompt":
                # A tool call the schema rejected, or a rule violation the
                # model has to work around. Worth recording — it explains
                # tool-call counts that otherwise look inflated, and it is
                # where a blocked business rule shows up.
                step = calls.get(getattr(part, "tool_call_id", None))
                content = _clip(getattr(part, "content", "validation error"), MAX_RESULT_CHARS)
                if step is not None:
                    step["status"] = "refused_or_retried"
                    step["result_summary"] = content
                else:
                    steps.append({
                        "iteration": iteration,
                        "action": "retry",
                        "tool_name": getattr(part, "tool_name", None),
                        "tool_args": "",
                        "result_summary": content,
                        "status": "refused_or_retried",
                    })

    return steps, thinking


def _load() -> list[dict[str, Any]]:
    """Read the existing trail. Never discards it silently."""
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except Exception:
        # Unreadable: keep it rather than overwrite. An audit trail you can
        # quietly destroy is not an audit trail.
        backup = AUDIT_PATH.with_suffix(f".corrupt-{int(datetime.now().timestamp())}.json")
        try:
            AUDIT_PATH.replace(backup)
            logger.error("Audit trail was unreadable; preserved at %s", backup.name)
        except Exception:
            logger.exception("Audit trail unreadable and could not be preserved")
        return []
    return data if isinstance(data, list) else [data]


def record(
    *,
    run_id: str,
    agent: str,
    ticket_id: int | None,
    task: str,
    started_at: str,
    status: str,
    stop_reason: str,
    messages: list[Any] | None = None,
    usage: Any = None,
    finish_reason: str | None = None,
    result_summary: str | None = None,
    delegated_to: list[str] | None = None,
    depth: int = 0,
    error: str | None = None,
) -> str:
    """Append one agent run. Never raises — logging must not cost an answer."""
    entry_id = f"{run_id}:{agent}:{uuid.uuid4().hex[:6]}"
    try:
        steps, thinking = steps_from_messages(messages or [])

        # Tool calls the rules refused. The most interesting line in the file:
        # it is the business rules doing their job.
        refusals = [
            {"tool": s["tool_name"], "reason": s["result_summary"]}
            for s in steps
            if s["status"] == "refused_or_retried"
        ]

        entry: dict[str, Any] = {
            "entry_id": entry_id,
            "run_id": run_id,
            "agent": agent,
            "ticket_id": ticket_id,
            "task": _clip(task, MAX_TEXT_CHARS),
            "delegation_depth": depth,
            "started_at": started_at,
            "finished_at": now_iso(),
            "iterations": sum(1 for s in steps if s["action"] == "tool_call"),
            "steps": steps,
            "tools_used": sorted({
                s["tool_name"] for s in steps
                if s["action"] == "tool_call" and s["tool_name"]
            }),
            "rule_refusals": refusals,
            "delegated_to": delegated_to or [],
            "status": status,
            "stop_reason": stop_reason,
            "finish_reason": finish_reason,
            "model_reasoning_emitted": thinking,
        }
        if usage is not None:
            entry["usage"] = {
                "requests": getattr(usage, "requests", None),
                "tool_calls": getattr(usage, "tool_calls", None),
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            }
        if result_summary:
            entry["result_summary"] = _clip(result_summary, MAX_TEXT_CHARS)
        if error:
            entry["error"] = _clip(error, MAX_RESULT_CHARS)

        with _lock:
            trail = _load()
            trail.append(entry)
            AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Write beside, then rename, so an interrupted write cannot
            # truncate the history.
            tmp = AUDIT_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(trail, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(AUDIT_PATH)
    except Exception:
        logger.exception("Could not append to the audit trail")

    return entry_id
