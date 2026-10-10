"""FastAPI backend for the Campus Customs operations desk.

Six routes, for the React dashboard built in the next problem:

    GET  /tickets                  the three tickets and their status
    POST /tickets/{id}/run         run the agent team on one ticket
    GET  /events                   recent agent activity from the audit trail
    POST /approvals/{id}           a person approves or rejects a request
    GET  /cash                     the checking balance
    POST /reset                    restore the working database

Two rules shape the whole file:

**No database access here.** There is no `sqlite3` import and no `.db` path.
Every business figure comes through the MCP server, which is where the
business rules live. A backend that could read or write the database directly
would be a way to walk straight past them.

**The approval route is the only place money moves.** Agents raise requests;
a person decides; and only then does this backend call `record_payment` or
`create_purchase_order` — both of which re-check the rules themselves.

Run it:

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic_ai.exceptions import ModelRetry

from . import audit, config
from .agents import Team
from .mcp_client import build_toolset
from .models import (
    AgentName,
    ApprovalDecision,
    ApprovalResponse,
    ApprovalsResponse,
    ApprovalStatus,
    CashResponse,
    ErrorResponse,
    EventsResponse,
    EventView,
    PendingApproval,
    ResetResponse,
    RunStatus,
    RunTicketResponse,
    TicketsResponse,
    TicketView,
)
from .orchestrator import process_ticket

logger = logging.getLogger("campus_customs.api")

# One MCP connection for the whole process, opened at startup. Starting a
# subprocess per request would be slow and would lose the tool cache.
_toolset = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _toolset
    _toolset = build_toolset()
    await _toolset.__aenter__()
    logger.info("MCP server connected")
    try:
        yield
    finally:
        await _toolset.__aexit__(None, None, None)
        logger.info("MCP server closed")


app = FastAPI(
    title="Campus Customs — Operations Desk",
    version="1.0.0",
    description=(
        "Runs the five-agent team against the shop's open tickets. All data "
        "comes through the MCP server; no payment happens without a human."
    ),
    lifespan=lifespan,
)

# The React dev server runs on a different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MCPUnavailable(RuntimeError):
    """The MCP server could not be reached, so no data is trustworthy."""


async def mcp(tool: str, args: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool, turning failures into clear API errors.

    Every route goes through here, so there is one place that distinguishes
    "the tool refused for a business reason" from "the server is down".
    """
    if _toolset is None:
        raise MCPUnavailable("The MCP server is not connected.")
    try:
        return await _toolset.direct_call_tool(tool, args or {})
    except ModelRetry as exc:
        # The tool raised ToolError — a business rule said no, or the caller
        # asked for something that does not exist. The message is the rule's
        # own wording, so it is safe and useful to pass on as a 400. MCP
        # prefixes it with "Error executing tool <name>:"; strip that so the
        # reason leads.
        text = str(exc)
        marker = f"Error executing tool {tool}: "
        raise ValueError(text.replace(marker, "", 1)) from exc
    except Exception as exc:
        # Anything else is the connection, not the request.
        logger.exception("MCP call failed: %s", tool)
        raise MCPUnavailable(f"MCP tool '{tool}' failed: {exc}") from exc


def _fail(status_code: int, error: str, detail: str | None = None) -> JSONResponse:
    """Every failure comes back in the same JSON shape."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error, detail=detail).model_dump(),
    )


@app.exception_handler(MCPUnavailable)
async def _mcp_down(request, exc: MCPUnavailable):
    return _fail(503, "The shop data service is unavailable.", str(exc))


@app.exception_handler(ValueError)
async def _rule_violation(request, exc: ValueError):
    return _fail(400, str(exc))


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness, with enough detail to spot a broken link early."""
    try:
        tools = await _toolset.list_tools() if _toolset else []
        cash = await mcp("get_cash_position", {"account": "checking"})
        return {
            "ok": True,
            "mcp_connected": True,
            "mcp_tools": len(tools),
            "shop_date": cash.get("shop_date"),
            "agents_configured": config.is_configured(),
        }
    except Exception as exc:
        return {"ok": False, "mcp_connected": False, "detail": str(exc)}


# ==========================================================================
# 1. GET /tickets
# ==========================================================================


@app.get("/tickets", response_model=TicketsResponse)
async def get_tickets(include_closed: bool = Query(default=True)) -> TicketsResponse:
    """The three tickets, with their descriptions and whether they are open."""
    rows: list[dict] = []
    # Open ones come from the dedicated tool; the rest are fetched by id so a
    # resolved ticket still appears in the dashboard.
    open_rows = await mcp("list_open_tickets")
    open_ids = {t["id"] for t in open_rows}
    rows.extend(open_rows)

    if include_closed:
        for tid in (101, 102, 103):
            if tid in open_ids:
                continue
            try:
                detail = await mcp("get_ticket", {"ticket_id": tid})
                rows.append(detail["ticket"])
            except ValueError:
                continue  # ticket genuinely does not exist

    cash = await mcp("get_cash_position", {"account": "checking"})
    tickets = [
        TicketView(
            id=r["id"],
            type=r["type"],
            requester=r["requester"],
            subject=r["subject"],
            description=(r.get("notes") or "").strip(),
            status=r["status"],
            is_open=r["status"].lower() == "open",
            sku=r.get("sku"),
            size=r.get("size"),
            qty=r.get("qty"),
            lease_id=r.get("lease_id"),
            invoice_id=r.get("invoice_id"),
            created_at=r["created_at"],
        )
        for r in sorted(rows, key=lambda x: x["id"])
    ]
    return TicketsResponse(
        shop_date=cash.get("shop_date", ""), count=len(tickets), tickets=tickets
    )


# ==========================================================================
# 2. POST /tickets/{ticket_id}/run
# ==========================================================================


def _pending(rows: list[dict], ticket_id: int | None = None) -> list[PendingApproval]:
    out = []
    for r in rows:
        if ticket_id is not None and r.get("ticket_id") != ticket_id:
            continue
        out.append(PendingApproval(
            id=r["id"], kind=r["kind"], ticket_id=r.get("ticket_id"),
            ref_id=r.get("ref_id"), amount=float(r["amount"]),
            requested_by=r["requested_by"], reason=r["reason"],
            status=ApprovalStatus(r["status"]), created_at=r["created_at"],
            decided_at=r.get("decided_at"), decided_by=r.get("decided_by"),
            decision_note=r.get("decision_note"),
        ))
    return out


@app.post("/tickets/{ticket_id}/run", response_model=RunTicketResponse)
async def run_ticket(ticket_id: int) -> RunTicketResponse:
    """Run the agent team on one ticket.

    The Boss routes it, a specialist works it, the Boss reviews. Agents may
    request approvals; none of them can grant one.
    """
    if not config.is_configured():
        raise HTTPException(
            status_code=503,
            detail="The agent team is not configured, so tickets cannot be run.",
        )

    # Confirm the ticket exists before spending a model call on it.
    try:
        detail = await mcp("get_ticket", {"ticket_id": ticket_id})
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"No ticket #{ticket_id}. Known tickets are 101, 102 and 103.",
        )
    ticket = detail["ticket"]

    run_id = audit.new_run_id()
    # The team shares the API's open MCP connection, and gets the filtered
    # toolset — no decide_approval, no reset.
    team = Team(toolset=_toolset)

    try:
        outcome = await process_ticket(team, ticket, run_id)
    except Exception as exc:
        logger.exception("Agent run failed for ticket %s", ticket_id)
        return RunTicketResponse(
            ok=False, status=RunStatus.FAILED, run_id=run_id, ticket_id=ticket_id,
            message=f"The agent run did not complete: {type(exc).__name__}.",
        )

    approvals = _pending(await mcp("list_pending_approvals", {"status": "pending"}), ticket_id)

    if outcome.needs_human_approval or approvals:
        status = RunStatus.NEEDS_APPROVAL
    elif outcome.status == "resolved":
        status = RunStatus.RESOLVED
    elif outcome.status == "blocked":
        status = RunStatus.BLOCKED
    else:
        status = RunStatus.IN_PROGRESS

    # Which agents and tools actually appeared, read back from the audit trail
    # rather than from what the model claimed.
    agents, tools = _run_footprint(run_id)

    return RunTicketResponse(
        ok=True, status=status, run_id=run_id, ticket_id=ticket_id,
        assigned_to=outcome.assigned_to, routing_reason=outcome.routing_reason,
        resolution=outcome.resolution, ticket_status=outcome.status,
        blocked_by=outcome.blocked_by,
        needs_human_approval=bool(outcome.needs_human_approval or approvals),
        pending_approvals=approvals, draft_ids=outcome.draft_ids,
        agents_involved=agents, tools_called=tools,
        model_calls=team.model_calls, tool_calls=team.tool_calls,
        message=(
            f"{len(approvals)} request(s) waiting for a human decision."
            if approvals else outcome.resolution
        ),
    )


def _run_footprint(run_id: str) -> tuple[list[AgentName], list[str]]:
    """Which agents ran and which tools they called, from the audit trail."""
    entries = _read_audit()
    agents, tools = [], set()
    for e in entries:
        if e.get("run_id") != run_id:
            continue
        try:
            a = AgentName(e["agent"])
            if a not in agents:
                agents.append(a)
        except ValueError:
            pass
        tools.update(e.get("tools_used") or [])
    return agents, sorted(tools)


# ==========================================================================
# 3. GET /events
# ==========================================================================


def _read_audit() -> list[dict]:
    """Read the audit trail. A missing or broken file is not a crash."""
    if not audit.AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(audit.AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.error("Audit trail is not valid JSON")
        return []
    return data if isinstance(data, list) else []


def _describe(step: dict) -> str:
    """One readable line for a tool call, for the dashboard timeline."""
    tool = step.get("tool_name") or "?"
    if step.get("status") == "refused_or_retried":
        return f"{tool} — refused: {(step.get('result_summary') or '')[:110]}"
    args = step.get("tool_args") or ""
    return f"{tool}({args[:70]})" if args else tool


@app.get("/events", response_model=EventsResponse)
async def get_events(
    limit: int = Query(default=50, ge=1, le=500),
    run_id: str | None = None,
    ticket_id: int | None = None,
) -> EventsResponse:
    """Recent agent activity: who did what, with which tools, and when."""
    entries = _read_audit()
    total = len(entries)

    if run_id:
        entries = [e for e in entries if e.get("run_id") == run_id]
    if ticket_id is not None:
        entries = [e for e in entries if e.get("ticket_id") == ticket_id]

    # Newest first — a dashboard timeline reads downwards from now.
    entries = list(reversed(entries))[:limit]

    events = [
        EventView(
            entry_id=e.get("entry_id", ""),
            run_id=e.get("run_id", ""),
            agent=e.get("agent", "unknown"),
            ticket_id=e.get("ticket_id"),
            task=e.get("task", ""),
            started_at=e.get("started_at", ""),
            finished_at=e.get("finished_at", ""),
            status=e.get("status", ""),
            stop_reason=e.get("stop_reason"),
            iterations=e.get("iterations", 0),
            tools_used=e.get("tools_used") or [],
            actions=[_describe(s) for s in (e.get("steps") or [])
                     if s.get("action") in ("tool_call", "retry")],
            rule_refusals=e.get("rule_refusals") or [],
            delegated_to=e.get("delegated_to") or [],
            delegation_depth=e.get("delegation_depth", 0),
            result_summary=e.get("result_summary"),
        )
        for e in entries
    ]
    return EventsResponse(count=len(events), total_recorded=total, events=events)


# ==========================================================================
# 4. POST /approvals/{request_id}
# ==========================================================================


@app.get("/approvals", response_model=ApprovalsResponse)
async def list_approvals(
    status: str = Query(default="all", description="pending, approved, rejected, or all"),
    ticket_id: int | None = None,
) -> ApprovalsResponse:
    """Every approval request, so the dashboard can show an approvals queue.

    Added for the dashboard: the run route only returns approvals raised by
    that run, but the queue has to survive a page refresh and show decided
    ones too.
    """
    rows = await mcp("list_pending_approvals", {"status": status})
    approvals = _pending(rows, ticket_id)
    return ApprovalsResponse(
        count=len(approvals),
        pending_count=sum(1 for a in approvals if a.status == ApprovalStatus.PENDING),
        approvals=approvals,
    )


@app.post("/approvals/{request_id}", response_model=ApprovalResponse)
async def decide_approval(request_id: int, body: ApprovalDecision) -> ApprovalResponse:
    """A person approves or rejects a pending request.

    The only route in the system where money moves — and only after the
    decision is recorded. Every rule is re-checked by the MCP tool at the
    moment of execution, so an approval granted earlier cannot force through
    a payment the shop can no longer afford.
    """
    if body.decision not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
        raise HTTPException(status_code=422, detail="decision must be approved or rejected.")

    try:
        approval = await mcp("get_approval", {"approval_id": request_id})
    except ValueError:
        raise HTTPException(
            status_code=404, detail=f"No approval request #{request_id}."
        )

    if approval["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Approval #{request_id} was already {approval['status']} "
                f"by {approval.get('decided_by') or 'someone'}. It cannot be "
                "decided twice."
            ),
        )

    # --- rejection: record the decision, move no money -------------------
    if body.decision == ApprovalStatus.REJECTED:
        await mcp("decide_approval", {
            "approval_id": request_id, "decision": "rejected",
            "decided_by": body.decided_by, "note": body.note,
        })
        cash = await mcp("get_cash_position", {"account": body.account})
        return ApprovalResponse(
            ok=True, status="rejected", approval_id=request_id, decision="rejected",
            executed=False, amount=float(approval["amount"]),
            new_balance=float(cash["balance"]),
            message=(
                f"Approval #{request_id} rejected by {body.decided_by}. "
                "Nothing was paid and the balance is unchanged."
            ),
        )

    # --- approval: check affordability before recording the decision -----
    kind = approval["kind"]
    amount = float(approval["amount"])

    if kind != "price_override":
        cash = await mcp("get_cash_position", {"account": body.account})
        if amount > float(cash["balance"]):
            # Approving something unaffordable must not half-happen, so the
            # decision is not recorded at all.
            return ApprovalResponse(
                ok=False, status="blocked", approval_id=request_id,
                decision="not_recorded", executed=False, amount=amount,
                new_balance=float(cash["balance"]),
                message=(
                    f"Blocked: ${amount:,.2f} exceeds the ${float(cash['balance']):,.2f} "
                    "balance. The approval was left pending and no money moved."
                ),
            )

    await mcp("decide_approval", {
        "approval_id": request_id, "decision": "approved",
        "decided_by": body.decided_by, "note": body.note,
    })

    # --- execute ---------------------------------------------------------
    try:
        if kind in ("invoice_payment", "rent_payment"):
            result = await mcp("record_payment", {
                "approval_id": request_id, "account": body.account,
            })
            return ApprovalResponse(
                ok=True, status="executed", approval_id=request_id,
                decision="approved", executed=True,
                payment_id=result["payment_id"], amount=result["amount"],
                new_balance=result["new_balance"], message=result["message"],
            )

        if kind == "purchase_order":
            details = json.loads(approval.get("details_json") or "{}")
            missing = [k for k in ("vendor_id", "sku", "qty") if not details.get(k)]
            if missing:
                return ApprovalResponse(
                    ok=False, status="blocked", approval_id=request_id,
                    decision="approved", executed=False, amount=amount,
                    message=(
                        f"Approved, but the order cannot be placed: the request is "
                        f"missing {', '.join(missing)}. Ask the agent to raise it again "
                        "with full details."
                    ),
                )
            result = await mcp("create_purchase_order", {
                "approval_id": request_id, "vendor_id": int(details["vendor_id"]),
                "sku": details["sku"], "qty": int(details["qty"]),
                "created_by": f"approved by {body.decided_by}",
                "size": details.get("size"), "ticket_id": approval.get("ticket_id"),
            })
            return ApprovalResponse(
                ok=True, status="executed", approval_id=request_id,
                decision="approved", executed=True,
                purchase_order_id=result["purchase_order_id"],
                amount=result["total_cost"], message=result["message"],
            )

        # price_override: approving it IS the action. No money moves.
        return ApprovalResponse(
            ok=True, status="executed", approval_id=request_id, decision="approved",
            executed=False, amount=amount,
            message=(
                f"Price override #{request_id} approved by {body.decided_by}. "
                "No cash moved; the agreed price may now be quoted."
            ),
        )

    except ValueError as exc:
        # The decision stands, but execution hit a rule — a blocked vendor, a
        # duplicate payment. Report it plainly rather than pretending it worked.
        return ApprovalResponse(
            ok=False, status="blocked", approval_id=request_id, decision="approved",
            executed=False, amount=amount,
            message=f"Approved, but the action was refused: {exc}",
        )


# ==========================================================================
# 5. GET /cash
# ==========================================================================


@app.get("/cash", response_model=CashResponse)
async def get_cash(account: str = Query(default="checking")) -> CashResponse:
    """The current balance, plus what is already committed."""
    pos = await mcp("get_cash_position", {"account": account})
    return CashResponse(
        account=pos["account"], balance=float(pos["balance"]),
        committed_by_open_requests=float(pos["committed_by_open_requests"]),
        available_to_commit=float(pos["available_to_commit"]),
        as_of=pos.get("as_of", ""), shop_date=pos.get("shop_date", ""),
    )


# ==========================================================================
# 6. POST /reset
# ==========================================================================


@app.post("/reset", response_model=ResetResponse)
async def reset(keep_audit: bool = Query(default=True)) -> ResetResponse:
    """Restore the working database and clear the run state.

    The original `campus_customs.db` is only read, never written.

    The audit trail is kept by default: it is the record of what happened,
    and resetting the shop does not unhappen it. Pass `keep_audit=false` to
    archive it to a timestamped file — it is moved aside, not deleted.
    """
    result = await mcp("reset_working_database")

    archived = 0
    if not keep_audit and audit.AUDIT_PATH.exists():
        entries = _read_audit()
        archived = len(entries)
        stamp = audit.now_iso().replace(":", "").replace("-", "")
        audit.AUDIT_PATH.replace(audit.AUDIT_PATH.with_name(f"audit_trail.{stamp}.json"))

    return ResetResponse(
        reset=True, restored_from=result["restored_from"],
        row_counts=result["row_counts"],
        checking_balance=result["checking_balance"],
        audit_entries_archived=archived,
        message=result["message"] + (
            f" {archived} audit entries archived." if archived else
            " The audit trail was kept."
        ),
    )
