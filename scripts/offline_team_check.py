"""Verify the agent team's wiring without making a single model call.

Uses PydanticAI's `TestModel`, which produces a valid structured response
locally. That exercises the parts worth checking mechanically — routing,
delegation limits, audit appending, tool registration — and leaves the model's
judgement to a real run.

    python scripts/offline_team_check.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai.models.test import TestModel  # noqa: E402

from backend import audit, config  # noqa: E402
from backend.agents import COLLEAGUES, Team  # noqa: E402
from backend.models import AgentName, TeamDeps  # noqa: E402
from backend.orchestrator import route_ticket  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(label: str, got, expected) -> None:
    ok = got == expected
    results.append((PASS if ok else FAIL, label, "" if ok else f"got {got!r}, expected {expected!r}"))


async def main() -> int:
    print("=" * 74)
    print("1. Routing — decided from the ticket, with no model call")
    print("=" * 74)
    cases = [
        ({"id": 101, "type": "customer_order", "sku": "CC-TEE-WHITE"}, AgentName.CUSTOMER_SERVICE),
        ({"id": 102, "type": "rent_notice", "lease_id": 1}, AgentName.FACILITIES),
        ({"id": 103, "type": "price_override", "sku": "CC-HOOD-NAVY"}, AgentName.ACCOUNTING),
        ({"id": 200, "type": "inventory_issue", "sku": "X"}, AgentName.INVENTORY),
        ({"id": 201, "type": "mystery", "lease_id": 1}, AgentName.FACILITIES),
        ({"id": 202, "type": "mystery", "invoice_id": 9}, AgentName.ACCOUNTING),
        ({"id": 203, "type": "mystery", "sku": "X"}, AgentName.INVENTORY),
        ({"id": 204, "type": "mystery"}, AgentName.BOSS),
    ]
    for ticket, expected in cases:
        agent, reason = route_ticket(ticket)
        check(f"ticket type '{ticket['type']}' -> {expected.value}", agent, expected)
        print(f"  #{ticket['id']:<4} {ticket['type']:<16} -> {agent.value:<17} {reason}")

    print()
    print("=" * 74)
    print("2. Delegation graph")
    print("=" * 74)
    async with Team() as team:
        tools = await team.toolset.list_tools()
        check("all 16 MCP tools reach the agents", len(tools), 16)
        print(f"  {len(tools)} MCP tools shared by all five agents")
        print()

        for name, agent in team.agents.items():
            fn_tools = sorted(
                t for t in (await agent.get_tools(None)) if t.startswith("ask_")
            ) if hasattr(agent, "get_tools") else []
            expected = sorted(f"ask_{c.value}" for c in COLLEAGUES[name])
            # Fall back to the registry when get_tools is unavailable.
            if not fn_tools:
                fn_tools = sorted(
                    n for n in getattr(agent._function_toolset, "tools", {}) if n.startswith("ask_")
                )
            check(f"{name.value} delegation tools", fn_tools, expected)
            print(f"  {name.value:<17} {fn_tools}")

        print()
        print("=" * 74)
        print("3. Delegation depth guard (no recursion possible)")
        print("=" * 74)
        # At the limit, an ask_* tool must refuse rather than run an agent.
        deps_at_limit = TeamDeps(
            ticket_id=101, ticket_type="customer_order",
            acting_agent=AgentName.CUSTOMER_SERVICE,
            depth=config.MAX_DELEGATION_DEPTH, run_id="offline-check",
        )
        cs = team.agents[AgentName.CUSTOMER_SERVICE]
        tool = cs._function_toolset.tools["ask_inventory"]
        fn = tool.function

        class Ctx:
            deps = deps_at_limit

        refusal = await fn(Ctx(), "Do we have size S?")
        refused = "limit reached" in refusal.lower()
        check("ask_* refuses at the depth limit", refused, True)
        print(f"  depth {config.MAX_DELEGATION_DEPTH}: {refusal[:100]}")

        print()
        print("=" * 74)
        print("4. An agent run appends to the audit trail (TestModel, no API call)")
        print("=" * 74)
        before = len(json.loads(audit.AUDIT_PATH.read_text(encoding="utf-8"))) if audit.AUDIT_PATH.exists() else 0

        inv = team.agents[AgentName.INVENTORY]
        # call_tools=[] keeps TestModel from invoking write tools.
        with inv.override(model=TestModel(call_tools=[])):
            deps = TeamDeps(
                ticket_id=101, ticket_type="customer_order",
                acting_agent=AgentName.INVENTORY, depth=0, run_id="offline-check",
            )
            run = await team.run_agent(AgentName.INVENTORY, "Offline wiring check.", deps)

        after_raw = json.loads(audit.AUDIT_PATH.read_text(encoding="utf-8"))
        after = len(after_raw)
        check("audit trail grew by exactly one entry", after - before, 1)
        check("entry records the acting agent", after_raw[-1]["agent"], "inventory")
        check("entry records the ticket", after_raw[-1]["ticket_id"], 101)
        check("output is forced to the real agent", run.output.agent, AgentName.INVENTORY)
        print(f"  entries {before} -> {after}; last = {after_raw[-1]['agent']} "
              f"on ticket {after_raw[-1]['ticket_id']}, status {after_raw[-1]['status']}")

        print()
        print("=" * 74)
        print("5. Audit trail is append-only")
        print("=" * 74)
        first_id = after_raw[0]["entry_id"]
        with inv.override(model=TestModel(call_tools=[])):
            deps = TeamDeps(ticket_id=102, ticket_type="rent_notice",
                            acting_agent=AgentName.INVENTORY, depth=0, run_id="offline-check")
            await team.run_agent(AgentName.INVENTORY, "Second offline check.", deps)
        final = json.loads(audit.AUDIT_PATH.read_text(encoding="utf-8"))
        check("earlier entries survive a later write", final[0]["entry_id"], first_id)
        check("trail grew again", len(final), after + 1)
        print(f"  {len(final)} entries; first entry_id still {final[0]['entry_id']}")

    print()
    print("=" * 74)
    failed = [r for r in results if r[0] == FAIL]
    for status, label, detail in results:
        if status == FAIL:
            print(f"  FAIL  {label}: {detail}")
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    print("=" * 74)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
