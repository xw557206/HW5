"""Runs tickets through the agent team.

The shape of a run:

    for each open ticket
        route it to a specialist        (no model call — see route_ticket)
        run that specialist             (1 model run, may delegate)
        run the Boss to review          (1 model run)

Routing is deliberately **not** a model decision. The ticket `type` column
already says what a ticket is, and spending a model call to rediscover that
is waste. The Boss still reviews every outcome, so judgement is applied where
it is actually needed — on the answer, not on the filing.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from . import audit, config
from .agents import Team
from .models import (
    DEFAULT_ROUTING,
    AgentFinding,
    AgentName,
    RunSummary,
    TeamDeps,
    TicketOutcome,
)


def route_ticket(ticket: dict[str, Any]) -> tuple[AgentName, str]:
    """Pick the owning agent from the ticket itself. No model call.

    Falls back to the Boss only when the type is one we have no rule for,
    which is the case worth a model's judgement.
    """
    ttype = (ticket.get("type") or "").lower()
    if ttype in DEFAULT_ROUTING:
        agent = DEFAULT_ROUTING[ttype]
        return agent, f"Ticket type '{ttype}' is owned by the {agent.value} agent."

    # Unknown type: look at what it references rather than guessing blindly.
    if ticket.get("lease_id"):
        return AgentName.FACILITIES, "Ticket references a lease, so Facilities owns it."
    if ticket.get("invoice_id"):
        return AgentName.ACCOUNTING, "Ticket references an invoice, so Accounting owns it."
    if ticket.get("sku"):
        return AgentName.INVENTORY, "Ticket references a product, so Inventory owns it."
    return AgentName.BOSS, f"Unrecognised ticket type '{ttype}'; the Boss will triage it."


def _specialist_task(ticket: dict[str, Any]) -> str:
    """The brief handed to the owning specialist."""
    return (
        f"Handle ticket #{ticket['id']} ({ticket['type']}) from {ticket['requester']}: "
        f"\"{ticket['subject']}\". Notes: {ticket.get('notes') or 'none'}. "
        "Start with get_ticket to read it in full. Establish the facts with your "
        "tools, do what the rules allow, and report what is blocked and what a "
        "human must decide."
    )


def _boss_task(ticket: dict[str, Any], finding: AgentFinding, owner: AgentName) -> str:
    """The brief handed to the Boss for review."""
    return (
        f"Ticket #{ticket['id']} ({ticket['type']}) was assigned to the "
        f"{owner.value} agent, who reported:\n\n"
        f"Summary: {finding.summary}\n"
        f"Actions: {'; '.join(finding.actions_taken) or 'none'}\n"
        f"Blocked by: {finding.blocked_by or 'nothing'}\n"
        f"Approvals: {finding.approval_ids or 'none'} | Drafts: {finding.draft_ids or 'none'}\n"
        f"Recommended status: {finding.recommended_status}\n\n"
        "Review this. Was anything verified by assumption rather than by a tool? "
        "Is there a cash or vendor consequence they missed? Then give your "
        "verdict: what happened, where the ticket stands, what blocks it, and "
        "the single next step for a human. Do not re-do their work."
    )


async def process_ticket(team: Team, ticket: dict[str, Any], run_id: str) -> TicketOutcome:
    """One ticket, start to finish."""
    owner, reason = route_ticket(ticket)

    deps = TeamDeps(
        ticket_id=ticket["id"],
        ticket_type=ticket["type"],
        acting_agent=owner,
        depth=0,
        run_id=run_id,
    )

    specialist = await team.run_agent(owner, _specialist_task(ticket), deps)
    finding = specialist.output

    boss_deps = TeamDeps(
        ticket_id=ticket["id"],
        ticket_type=ticket["type"],
        acting_agent=AgentName.BOSS,
        # The Boss reviews rather than investigates, so it starts at the
        # delegation limit: it may not spawn another round of specialists.
        depth=config.MAX_DELEGATION_DEPTH,
        run_id=run_id,
    )
    boss = await team.run_agent(AgentName.BOSS, _boss_task(ticket, finding, owner), boss_deps)
    verdict = boss.output

    return TicketOutcome(
        ticket_id=ticket["id"],
        ticket_type=ticket["type"],
        assigned_to=owner,
        routing_reason=reason,
        resolution=verdict.summary,
        status=verdict.recommended_status or finding.recommended_status,
        findings=[finding, verdict],
        blocked_by=verdict.blocked_by or finding.blocked_by,
        needs_human_approval=finding.needs_human_approval or verdict.needs_human_approval,
        approval_ids=sorted(set(finding.approval_ids + verdict.approval_ids)),
        draft_ids=sorted(set(finding.draft_ids + verdict.draft_ids)),
        next_step_for_human=(
            verdict.blocked_by or finding.blocked_by
            if (verdict.needs_human_approval or finding.needs_human_approval)
            else None
        ),
    )


async def run_open_tickets(ticket_ids: list[int] | None = None) -> RunSummary:
    """Process every open ticket, or just the ones named."""
    run_id = audit.new_run_id()
    started = audit.now_iso()
    outcomes: list[TicketOutcome] = []
    notes: list[str] = []

    async with Team() as team:
        # Tickets come from the MCP server, like everything else — the
        # backend holds no database connection of its own.
        raw = await team.toolset.direct_call_tool("list_open_tickets", {})
        tickets = raw if isinstance(raw, list) else json.loads(str(raw))

        if ticket_ids:
            tickets = [t for t in tickets if t["id"] in ticket_ids]

        shop = await team.toolset.direct_call_tool("get_cash_position", {})
        shop_date = (shop or {}).get("shop_date", "")

        for ticket in tickets:
            try:
                outcomes.append(await process_ticket(team, ticket, run_id))
            except Exception as exc:
                notes.append(f"Ticket #{ticket['id']} failed: {type(exc).__name__}: {exc}")

        return RunSummary(
            run_id=run_id,
            started_at=started,
            finished_at=audit.now_iso(),
            shop_date=shop_date,
            tickets_processed=len(outcomes),
            outcomes=outcomes,
            model_calls=team.model_calls,
            tool_calls=team.tool_calls,
            notes=notes,
        )


def main() -> None:
    if not config.is_configured():
        raise SystemExit("PORTKEY_API_KEY is not set — add it to .env first.")
    summary = asyncio.run(run_open_tickets())
    print(f"\nrun {summary.run_id} — {summary.tickets_processed} ticket(s), "
          f"{summary.model_calls} model calls, {summary.tool_calls} tool calls\n")
    for o in summary.outcomes:
        print(f"  #{o.ticket_id} {o.ticket_type} -> {o.assigned_to.value} [{o.status}]")
        print(f"     {o.resolution}")
        if o.blocked_by:
            print(f"     blocked: {o.blocked_by}")
        if o.approval_ids:
            print(f"     approvals: {o.approval_ids}")
        if o.draft_ids:
            print(f"     drafts: {o.draft_ids}")
        print()


if __name__ == "__main__":
    main()
