"""Structured types for the agent team.

Typed outputs mean the orchestrator and the dashboard can branch on fields
rather than parse prose — `outcome.blocked_by` is checkable, "it seems the
vendor is blocked" is not.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    """The five agents. Used for routing, delegation and audit records."""

    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


# Which agent owns which kind of ticket. Deterministic, so the obvious cases
# cost no model call at all — see `route_ticket` in orchestrator.py.
DEFAULT_ROUTING: dict[str, AgentName] = {
    "customer_order": AgentName.CUSTOMER_SERVICE,
    "rent_notice": AgentName.FACILITIES,
    "price_override": AgentName.ACCOUNTING,
    "inventory_issue": AgentName.INVENTORY,
    "invoice": AgentName.ACCOUNTING,
    "unpaid_bill": AgentName.ACCOUNTING,
}


class Delegation(BaseModel):
    """One agent asking another for help."""

    to: AgentName
    question: str = Field(description="What is being asked, in plain words.")
    answer: str | None = Field(
        default=None, description="What came back. None while still in flight."
    )


class AgentFinding(BaseModel):
    """What a specialist concluded about a ticket.

    This is the hand-back shape: the Boss reads these, not raw transcripts.
    """

    agent: AgentName
    ticket_id: int

    summary: str = Field(description="What was found and done, in two or three sentences.")
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Concrete things done — drafts written, approvals requested, "
        "statuses changed. Empty when the agent only looked.",
    )
    blocked_by: str | None = Field(
        default=None,
        description="What stops this being finished, if anything. A business "
        "rule, missing stock, or a decision only a human can make.",
    )
    needs_human_approval: bool = Field(
        default=False, description="True when an approval is waiting on a person."
    )
    approval_ids: list[int] = Field(
        default_factory=list, description="Approvals this agent raised."
    )
    draft_ids: list[int] = Field(
        default_factory=list, description="Drafts this agent wrote."
    )
    delegated_to: list[AgentName] = Field(
        default_factory=list, description="Colleagues consulted during this run."
    )
    recommended_status: str = Field(
        default="in_progress",
        description="open, in_progress, waiting_approval, resolved, or blocked.",
    )


class TicketOutcome(BaseModel):
    """The Boss's verdict on one ticket, after the specialists have reported."""

    ticket_id: int
    ticket_type: str
    assigned_to: AgentName = Field(description="The agent given the ticket.")
    routing_reason: str = Field(description="Why that agent, in one sentence.")

    resolution: str = Field(description="What happened to this ticket, in plain words.")
    status: str = Field(description="Where the ticket stands now.")

    findings: list[AgentFinding] = Field(default_factory=list)
    blocked_by: str | None = None
    needs_human_approval: bool = False
    approval_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)

    next_step_for_human: str | None = Field(
        default=None,
        description="The one thing a person should do next, if anything.",
    )


class TeamDeps(BaseModel):
    """Shared context passed to every agent in a run.

    `depth` is the delegation guard: it rises with each hop and the delegate
    tools refuse past the limit, so two agents cannot consult each other in
    circles.
    """

    ticket_id: int
    ticket_type: str = ""
    acting_agent: AgentName = AgentName.BOSS
    depth: int = 0
    run_id: str = ""

    model_config = {"arbitrary_types_allowed": True}


class RunSummary(BaseModel):
    """Everything one orchestrator run produced."""

    run_id: str
    started_at: str
    finished_at: str
    shop_date: str
    tickets_processed: int
    outcomes: list[TicketOutcome] = Field(default_factory=list)
    model_calls: int = 0
    tool_calls: int = 0
    notes: list[str] = Field(default_factory=list)


# ==========================================================================
# API shapes
#
# Every response carries `ok` and `status`, so the dashboard can branch on
# two fields instead of guessing from an HTTP code.
# ==========================================================================


class RunStatus(str, Enum):
    """What happened when a ticket was run."""

    RESOLVED = "resolved"
    NEEDS_APPROVAL = "needs_approval"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TicketView(BaseModel):
    """One ticket as the dashboard shows it."""

    id: int
    type: str
    requester: str
    subject: str
    description: str = Field(description="The ticket's notes, in plain words.")
    status: str
    is_open: bool
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    created_at: str


class TicketsResponse(BaseModel):
    ok: bool = True
    shop_date: str
    count: int
    tickets: list[TicketView] = Field(default_factory=list)


class PendingApproval(BaseModel):
    """An approval waiting on a person, shaped for the dashboard."""

    id: int
    kind: str
    ticket_id: int | None = None
    ref_id: int | None = None
    amount: float
    requested_by: str
    reason: str
    status: ApprovalStatus
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_note: str | None = None


class RunTicketResponse(BaseModel):
    """The result of running one ticket through the team."""

    ok: bool = True
    status: RunStatus
    run_id: str
    ticket_id: int
    assigned_to: AgentName | None = None
    routing_reason: str | None = None
    resolution: str = ""
    ticket_status: str = ""
    blocked_by: str | None = None
    needs_human_approval: bool = False
    pending_approvals: list[PendingApproval] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    agents_involved: list[AgentName] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    model_calls: int = 0
    tool_calls: int = 0
    message: str = ""


class EventView(BaseModel):
    """One agent action, as the dashboard timeline shows it."""

    entry_id: str
    run_id: str
    agent: str
    ticket_id: int | None = None
    task: str = ""
    started_at: str
    finished_at: str
    status: str
    stop_reason: str | None = None
    iterations: int = 0
    tools_used: list[str] = Field(default_factory=list)
    actions: list[str] = Field(
        default_factory=list, description="One readable line per tool call."
    )
    rule_refusals: list[dict] = Field(
        default_factory=list, description="Where a business rule refused the agent."
    )
    delegated_to: list[str] = Field(default_factory=list)
    delegation_depth: int = 0
    result_summary: str | None = None


class EventsResponse(BaseModel):
    ok: bool = True
    count: int
    total_recorded: int
    events: list[EventView] = Field(default_factory=list)


class ApprovalsResponse(BaseModel):
    """Every approval the dashboard knows about, pending or decided."""

    ok: bool = True
    count: int
    pending_count: int
    approvals: list["PendingApproval"] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    """A person approving or rejecting a request."""

    decision: ApprovalStatus = Field(description="approved or rejected.")
    decided_by: str = Field(min_length=1, description="Who is deciding. Recorded.")
    note: str = ""
    account: str = "checking"


class ApprovalResponse(BaseModel):
    ok: bool
    status: str = Field(description="executed, rejected, or blocked.")
    approval_id: int
    decision: str
    executed: bool = Field(
        default=False, description="True only when money actually moved."
    )
    payment_id: int | None = None
    purchase_order_id: int | None = None
    amount: float | None = None
    new_balance: float | None = None
    message: str


class CashResponse(BaseModel):
    ok: bool = True
    account: str
    balance: float
    committed_by_open_requests: float = 0.0
    available_to_commit: float = 0.0
    as_of: str = ""
    shop_date: str = ""


class ResetResponse(BaseModel):
    ok: bool = True
    reset: bool
    restored_from: str
    row_counts: dict[str, int] = Field(default_factory=dict)
    checking_balance: float
    audit_entries_archived: int = 0
    message: str


class ErrorResponse(BaseModel):
    """Every failure comes back in this shape, never as a bare string."""

    ok: bool = False
    status: str = "error"
    error: str
    detail: str | None = None
