"""Campus Customs MCP server.

Three tools, one for each of the three open tickets:

    check_order_fulfillment   ticket 101  customer order, out-of-stock size
    check_rent_due            ticket 102  rent notice
    quote_bulk_discount       ticket 103  bulk price override

Every number the tools return is read from `data/campus_customs_new.db` or
computed from it by plain arithmetic. Nothing is invented: when the database
has no answer, the tool says so rather than guessing.

Run it (not required yet):

    python -m mcp_server.server

Note on the library. The assignment asks for FastMCP. The installed SDK is
`mcp` 2.2.0, where **FastMCP was renamed to `MCPServer`** — same decorator
API, new name. Importing `mcp.server.fastmcp` on this version fails outright,
so `MCPServer` is the correct successor to use here.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
# ToolError's message reaches the client intact; a plain exception is
# replaced with a generic "Error executing tool X", which loses the reason
# a business rule said no.
from mcp.server.mcpserver.exceptions import ToolError

from . import db, ops
from .models import BulkQuote, OrderFulfillment, RentStatus, SizeStock, VendorOption
from .schema import ensure_schema

# The agent tables (approvals, drafts, purchase_orders) are created on import
# so the server is usable from a cold start.
with db.connect() as _conn:
    ensure_schema(_conn)

server = MCPServer(
    name="campus-customs",
    instructions=(
        "Operations data for the Campus Customs shop: inventory, pricing, "
        "vendors, invoices, leases and cash. All figures come from the shop "
        "database. Dates are judged against the shop's own date "
        "(desk.date_today), not today's real date. These tools are read-only "
        "— they never move money and never place an order."
    ),
)


def _match_vendors(sku: str) -> list[VendorOption]:
    """Vendors whose specialty could supply this product, with their standing.

    Matching is on the product's own words. An apparel item needs an apparel
    vendor; a courier cannot print a tee shirt. Each candidate is then checked
    for unpaid invoices, because a vendor who is owed money cannot be given a
    new order.
    """
    name = (db.product_name(sku) or "").lower()
    sku_l = sku.lower()
    is_apparel = any(w in sku_l or w in name for w in ("tee", "hood", "shirt", "apparel"))
    is_small_good = any(w in sku_l or w in name for w in ("mug", "hat", "cap", "crest"))

    options: list[VendorOption] = []
    for v in db.vendors():
        specialty = v["specialty"].lower()
        relevant = (
            (is_apparel and "apparel" in specialty)
            or (is_small_good and ("mug" in specialty or "small goods" in specialty))
        )
        if not relevant:
            continue

        unpaid = db.outstanding_invoices(v["id"])
        total = sum(float(i["amount"]) for i in unpaid)
        blocked = len(unpaid) > 0
        reason = None
        if blocked:
            refs = ", ".join(
                f"#{i['id']} ${i['amount']:,.2f} due {i['due_date']}" for i in unpaid
            )
            reason = (
                f"{v['name']} has {len(unpaid)} unpaid invoice(s) totalling "
                f"${total:,.2f} ({refs}). No new orders until settled."
            )
        options.append(
            VendorOption(
                vendor_id=v["id"],
                name=v["name"],
                specialty=v["specialty"],
                lead_days=v["lead_days"],
                outstanding_invoice_count=len(unpaid),
                outstanding_invoice_total=round(total, 2),
                can_order=not blocked,
                blocked_reason=reason,
            )
        )
    return options


@server.tool(
    name="check_order_fulfillment",
    title="Check whether a customer order can be filled",
    description=(
        "For a customer order (ticket 101): how many units of the requested "
        "sku and size are on the shelf, what other sizes exist, and — when "
        "stock is short — which vendors could restock it and whether any of "
        "them is blocked by an unpaid invoice. Read-only."
    ),
)
def check_order_fulfillment(sku: str, size: str, qty: int = 1) -> OrderFulfillment:
    """Answer the question ticket 101 actually asks: can we ship this today?

    Args:
        sku: Catalogue code, e.g. "CC-TEE-WHITE".
        size: Requested size, e.g. "S".
        qty: Units requested. Defaults to 1.
    """
    row = db.stock_for(sku, size)
    # A missing row and a row at zero are different facts, and both mean
    # "cannot ship". Reporting them separately keeps the reply honest.
    on_hand = int(row["qty"]) if row else 0
    name = db.product_name(sku)

    sizes = [
        SizeStock(
            size=s["size"], qty=int(s["qty"]), location=s["location"], in_stock=s["qty"] > 0
        )
        for s in db.all_sizes_for(sku)
    ]
    price = db.pricing_for(sku)
    shortfall = max(0, qty - on_hand)
    options = _match_vendors(sku) if shortfall else []
    any_available = any(o.can_order for o in options)

    if name is None:
        summary = f"{sku} is not in the catalogue, so nothing can be promised."
    elif shortfall == 0:
        summary = f"{name} in size {size}: {on_hand} on hand, enough for {qty}."
    else:
        stocked = [s.size for s in sizes if s.in_stock]
        parts = [
            f"{name} in size {size} is "
            + ("not carried" if row is None else f"out of stock (qty {on_hand})")
            + f"; short {shortfall} of {qty}."
        ]
        parts.append(
            f"Other sizes in stock: {', '.join(stocked)}." if stocked
            else "No other size is in stock either."
        )
        if not options:
            parts.append("No vendor in the database matches this product type.")
        elif any_available:
            ok = [o for o in options if o.can_order]
            parts.append(
                "Could restock from "
                + "; ".join(f"{o.name} ({o.lead_days}-day lead)" for o in ok)
                + "."
            )
        else:
            parts.append(
                "Every matching vendor is blocked: "
                + " ".join(o.blocked_reason or "" for o in options)
            )
        summary = " ".join(parts)

    return OrderFulfillment(
        sku=sku,
        product_name=name,
        requested_size=size,
        requested_qty=qty,
        qty_on_hand=on_hand,
        can_fulfill_now=shortfall == 0 and name is not None,
        shortfall=shortfall,
        other_sizes=sizes,
        unit_cost=float(price["unit_cost"]) if price else None,
        list_price=float(price["list_price"]) if price else None,
        restock_options=options,
        any_vendor_available=any_available,
        shop_date=db.today().isoformat(),
        summary=summary,
    )


@server.tool(
    name="check_rent_due",
    title="Check rent owed on a lease",
    description=(
        "For a rent notice (ticket 102): the rent amount, when it is due "
        "relative to the shop's own date, whether cash covers it, and whether "
        "it has already been paid. Read-only — it never makes a payment."
    ),
)
def check_rent_due(lease_id: int = 1, account: str = "checking") -> RentStatus:
    """Answer the question ticket 102 asks: what is owed, when, can we pay it?

    Args:
        lease_id: Which lease. Defaults to 1, the only lease on file.
        account: Cash account to check. Defaults to "checking".
    """
    row = db.lease(lease_id)
    if row is None:
        known = ", ".join(str(l["id"]) for l in db.leases()) or "none"
        raise ToolError(f"No lease with id {lease_id}. Leases on file: {known}.")

    rent = float(row["monthly_rent"])
    days = db.days_until(row["next_due"])

    cash = db.cash_balance(account)
    if cash is None:
        raise ToolError(f"No cash account named '{account}'.")
    balance = float(cash["balance"])

    prior = db.payments_for("rent", lease_id)
    affordable = balance >= rent

    when = (
        f"overdue by {abs(days)} day(s)" if days < 0
        else "due today" if days == 0
        else f"due in {days} day(s)"
    )
    if prior:
        summary = (
            f"Rent for {row['space_name']} is already recorded as paid "
            f"({len(prior)} payment(s))."
        )
    else:
        summary = (
            f"{row['space_name']}: ${rent:,.2f} to {row['landlord']}, "
            f"{when} on {row['next_due']}. Checking holds ${balance:,.2f}, "
            + (
                f"leaving ${balance - rent:,.2f} after payment."
                if affordable
                else f"which is ${rent - balance:,.2f} short."
            )
            + " Payment requires human approval."
        )

    return RentStatus(
        lease_id=row["id"],
        space_name=row["space_name"],
        landlord=row["landlord"],
        monthly_rent=rent,
        next_due=row["next_due"],
        days_until_due=days,
        is_overdue=days < 0,
        is_due_soon=0 <= days <= 7,
        cash_account=cash["name"],
        cash_balance=balance,
        affordable=affordable,
        balance_after_payment=round(balance - rent, 2),
        already_paid=bool(prior),
        payment_count=len(prior),
        shop_date=db.today().isoformat(),
        summary=summary,
    )


@server.tool(
    name="quote_bulk_discount",
    title="Price a bulk order and test a proposed discount",
    description=(
        "For a bulk discount request (ticket 103): how much of the requested "
        "size is on hand, the cost and list price, the break-even floor, and "
        "— when a price is proposed — whether it still makes money. "
        "Read-only; it recommends but never applies a price change."
    ),
)
def quote_bulk_discount(
    sku: str, size: str, qty: int, proposed_unit_price: float | None = None
) -> BulkQuote:
    """Answer the question ticket 103 asks: can we supply it, and at what price?

    Args:
        sku: Catalogue code, e.g. "CC-HOOD-NAVY".
        size: Requested size, e.g. "M".
        qty: Units requested.
        proposed_unit_price: Optional per-unit price to test against cost.
    """
    price = db.pricing_for(sku)
    if price is None:
        raise ToolError(f"No pricing row for {sku}, so no quote can be given.")
    if qty <= 0:
        raise ToolError("Quantity must be a positive number of units.")

    unit_cost = float(price["unit_cost"])
    list_price = float(price["list_price"])

    row = db.stock_for(sku, size)
    on_hand = int(row["qty"]) if row else 0
    shortfall = max(0, qty - on_hand)

    list_total = qty * list_price
    cost_total = qty * unit_cost
    # The deepest discount that still breaks even, as a percentage off list.
    max_disc = (list_price - unit_cost) / list_price * 100 if list_price else 0.0

    p_total = p_margin = p_disc = None
    p_ok = None
    if proposed_unit_price is not None:
        p_total = round(qty * proposed_unit_price, 2)
        p_margin = round(p_total - cost_total, 2)
        p_disc = round((list_price - proposed_unit_price) / list_price * 100, 1) if list_price else 0.0
        p_ok = proposed_unit_price > unit_cost

    name = db.product_name(sku)
    bits = [
        f"{name or sku} size {size}: {on_hand} on hand against {qty} requested"
        + (f", short {shortfall}." if shortfall else ", enough to fill.")
    ]
    bits.append(
        f"Cost ${unit_cost:,.2f}/unit, list ${list_price:,.2f}/unit. "
        f"At list that is ${list_total:,.2f} with ${list_total - cost_total:,.2f} margin. "
        f"Break-even is ${unit_cost:,.2f}/unit ({max_disc:.0f}% off list)."
    )
    if proposed_unit_price is not None:
        bits.append(
            f"The proposed ${proposed_unit_price:,.2f}/unit is {p_disc}% off, "
            f"totalling ${p_total:,.2f} with ${p_margin:,.2f} margin — "
            + ("still profitable." if p_ok else "BELOW COST, it would lose money.")
        )
    bits.append("A price override needs human approval.")

    return BulkQuote(
        sku=sku,
        product_name=name,
        size=size,
        requested_qty=qty,
        qty_on_hand=on_hand,
        shortfall=shortfall,
        can_fill_from_stock=shortfall == 0,
        unit_cost=unit_cost,
        list_price=list_price,
        list_total=round(list_total, 2),
        cost_total=round(cost_total, 2),
        margin_at_list=round(list_total - cost_total, 2),
        min_unit_price=unit_cost,
        max_discount_pct_at_cost=round(max_disc, 1),
        proposed_unit_price=proposed_unit_price,
        proposed_total=p_total,
        proposed_margin=p_margin,
        proposed_discount_pct=p_disc,
        proposed_is_profitable=p_ok,
        shop_date=db.today().isoformat(),
        summary=" ".join(bits),
    )


# ==========================================================================
# Reading the work
# ==========================================================================


@server.tool(
    name="list_open_tickets",
    title="List the tickets still open",
    description="Every open ticket, so the Boss can see what needs handling. Read-only.",
)
def list_open_tickets() -> list[dict[str, Any]]:
    """The inbox. Each row carries the links the specialists will need."""
    return [dict(t) for t in db.open_tickets()]


@server.tool(
    name="get_ticket",
    title="Read one ticket with everything it links to",
    description=(
        "One ticket plus the lease or invoice it references, so an agent gets "
        "the full picture in a single call instead of three. Read-only."
    ),
)
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Resolve a ticket's foreign keys so the agent does not have to.

    Args:
        ticket_id: The ticket number.
    """
    row = db.ticket(ticket_id)
    if row is None:
        raise ToolError(f"No ticket #{ticket_id}.")
    out: dict[str, Any] = {"ticket": dict(row), "shop_date": db.today().isoformat()}

    if row["invoice_id"]:
        inv = db.invoice(row["invoice_id"])
        if inv:
            out["linked_invoice"] = dict(inv) | {
                "days_until_due": db.days_until(inv["due_date"]),
                "is_overdue": db.days_until(inv["due_date"]) < 0,
            }
    if row["lease_id"]:
        lease = db.lease(row["lease_id"])
        if lease:
            out["linked_lease"] = dict(lease) | {
                "days_until_due": db.days_until(lease["next_due"])
            }
    if row["sku"]:
        stock = db.stock_for(row["sku"], row["size"]) if row["size"] else None
        price = db.pricing_for(row["sku"])
        out["product"] = {
            "sku": row["sku"],
            "name": db.product_name(row["sku"]),
            "requested_size": row["size"],
            "qty_on_hand": int(stock["qty"]) if stock else 0,
            "all_sizes": {s["size"]: s["qty"] for s in db.all_sizes_for(row["sku"])},
            "unit_cost": float(price["unit_cost"]) if price else None,
            "list_price": float(price["list_price"]) if price else None,
        }
    return out


# ==========================================================================
# Money and vendors
# ==========================================================================


@server.tool(
    name="get_cash_position",
    title="How much the shop can actually spend",
    description=(
        "Balance, the total already committed to pending or approved requests, "
        "and what is genuinely left. Use this before committing money. Read-only."
    ),
)
def get_cash_position(account: str = "checking") -> dict[str, Any]:
    """Spendable cash, not just the raw balance.

    Args:
        account: Which account. Defaults to "checking".
    """
    return ops.cash_position(account)


@server.tool(
    name="list_outstanding_invoices",
    title="Bills the shop still owes",
    description=(
        "Every invoice not yet paid, with how many days overdue each is "
        "against the shop's date. Read-only."
    ),
)
def list_outstanding_invoices() -> list[dict[str, Any]]:
    """Unpaid bills, each with its overdue count."""
    out = []
    for inv in db.outstanding_invoices():
        days = db.days_until(inv["due_date"])
        out.append(dict(inv) | {
            "days_until_due": days,
            "is_overdue": days < 0,
            "days_overdue": abs(days) if days < 0 else 0,
        })
    return out


@server.tool(
    name="check_vendor_status",
    title="Check whether a vendor can be ordered from",
    description=(
        "Whether this vendor has unpaid invoices. The shop may not place new "
        "orders with a vendor it owes money to. Read-only."
    ),
)
def check_vendor_status(vendor_id: int) -> dict[str, Any]:
    """The order-blocking check, on demand.

    Args:
        vendor_id: Which vendor.
    """
    vendor = next((v for v in db.vendors() if v["id"] == vendor_id), None)
    if vendor is None:
        known = ", ".join(f"{v['id']}={v['name']}" for v in db.vendors())
        raise ToolError(f"No vendor with id {vendor_id}. Vendors: {known}.")

    unpaid = db.outstanding_invoices(vendor_id)
    total = sum(float(i["amount"]) for i in unpaid)
    return {
        "vendor_id": vendor["id"],
        "name": vendor["name"],
        "specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "unpaid_invoices": [dict(i) for i in unpaid],
        "unpaid_total": round(total, 2),
        "can_order": not unpaid,
        "message": (
            f"{vendor['name']} is clear to order from."
            if not unpaid
            else f"{vendor['name']} is BLOCKED: ${total:,.2f} unpaid across "
                 f"{len(unpaid)} invoice(s). Settle before ordering."
        ),
    }


# ==========================================================================
# Approvals — the only route to spending money or changing a price
# ==========================================================================


@server.tool(
    name="request_approval",
    title="Ask a human to approve money or a price change",
    description=(
        "Create a pending approval. This does NOT spend anything or change "
        "any price — it queues the request for a person to decide on the "
        "dashboard. Kinds: invoice_payment, rent_payment, purchase_order, "
        "price_override."
    ),
)
def request_approval(
    kind: str,
    amount: float,
    requested_by: str,
    reason: str,
    ref_id: int | None = None,
    ticket_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Queue a decision for a human.

    Args:
        kind: invoice_payment, rent_payment, purchase_order, or price_override.
        amount: Money involved, in dollars.
        requested_by: Which agent is asking.
        reason: Why, in plain words — a person reads this before deciding.
        ref_id: Invoice id, lease id, or vendor id, depending on kind.
        ticket_id: The ticket this relates to.
        details: Structured extras, e.g. sku, size, qty, proposed price.
    """
    try:
        return ops.request_approval(
            kind=kind, amount=amount, requested_by=requested_by, reason=reason,
            ref_id=ref_id, ticket_id=ticket_id, details=details,
        )
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


@server.tool(
    name="list_pending_approvals",
    title="Approvals waiting on a human",
    description="Everything queued for a decision, for the dashboard and for status checks.",
)
def list_pending_approvals(status: str = "pending") -> list[dict[str, Any]]:
    """Approvals filtered by status.

    Args:
        status: pending, approved, or rejected. Use "all" for everything.
    """
    return ops.list_approvals(None if status == "all" else status)


# ==========================================================================
# Acting on an approval
# ==========================================================================


@server.tool(
    name="record_payment",
    title="Pay something a human has approved",
    description=(
        "Move money against an APPROVED approval, update the balance and mark "
        "the invoice paid. Refuses unless the approval exists and is approved."
    ),
)
def record_payment(approval_id: int, account: str = "checking") -> dict[str, Any]:
    """Execute an approved payment.

    Args:
        approval_id: The approval authorising this. Must already be approved.
        account: Which account to pay from.
    """
    try:
        return ops.record_payment(approval_id, account)
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


@server.tool(
    name="create_purchase_order",
    title="Place a restock order",
    description=(
        "Create a purchase order against an APPROVED approval. Re-checks that "
        "the vendor has no unpaid invoices at the moment of ordering."
    ),
)
def create_purchase_order(
    approval_id: int,
    vendor_id: int,
    sku: str,
    qty: int,
    created_by: str,
    size: str | None = None,
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Order stock from a vendor.

    Args:
        approval_id: An approved purchase_order approval.
        vendor_id: Who to order from.
        sku: What to order.
        qty: How many units.
        created_by: Which agent is placing it.
        size: Size, where the product has sizes.
        ticket_id: The ticket this serves.
    """
    try:
        return ops.create_purchase_order(
            approval_id=approval_id, vendor_id=vendor_id, sku=sku, qty=qty,
            created_by=created_by, size=size, ticket_id=ticket_id,
        )
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


# ==========================================================================
# Communications — saved as drafts, never sent
# ==========================================================================


@server.tool(
    name="draft_customer_email",
    title="Write a customer email (saved as a draft)",
    description=(
        "Save a reply to a customer as a DRAFT. It is never sent — a person "
        "reviews and sends it. There is no send tool."
    ),
)
def draft_customer_email(
    recipient: str, subject: str, body: str, created_by: str, ticket_id: int | None = None
) -> dict[str, Any]:
    """Draft a customer reply.

    Args:
        recipient: Who it is to.
        subject: Subject line.
        body: The message. Only state facts the tools returned.
        created_by: Which agent wrote it.
        ticket_id: The ticket it answers.
    """
    try:
        return ops.save_draft("customer_email", recipient, subject, body, created_by, ticket_id)
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


@server.tool(
    name="draft_vendor_message",
    title="Write a vendor message (saved as a draft)",
    description=(
        "Save a message to a vendor as a DRAFT. Never sent. Use for chasing a "
        "reprint, querying an invoice, or asking about lead times."
    ),
)
def draft_vendor_message(
    recipient: str, subject: str, body: str, created_by: str, ticket_id: int | None = None
) -> dict[str, Any]:
    """Draft a vendor message.

    Args:
        recipient: Vendor name.
        subject: Subject line.
        body: The message.
        created_by: Which agent wrote it.
        ticket_id: The ticket it relates to.
    """
    try:
        return ops.save_draft("vendor_message", recipient, subject, body, created_by, ticket_id)
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


@server.tool(
    name="list_drafts",
    title="Drafts written so far",
    description="Every saved draft, none of which has been sent.",
)
def list_drafts(ticket_id: int | None = None) -> list[dict[str, Any]]:
    """Saved drafts, optionally for one ticket.

    Args:
        ticket_id: Limit to one ticket.
    """
    return ops.list_drafts(ticket_id)


# ==========================================================================
# Ticket progress
# ==========================================================================


@server.tool(
    name="update_ticket_status",
    title="Move a ticket along",
    description=(
        "Set a ticket's status and append a note recording who did what and "
        "why. Statuses: open, in_progress, waiting_approval, resolved, blocked."
    ),
)
def update_ticket_status(
    ticket_id: int, status: str, note: str, updated_by: str
) -> dict[str, Any]:
    """Record progress on a ticket.

    Args:
        ticket_id: Which ticket.
        status: open, in_progress, waiting_approval, resolved, or blocked.
        note: What happened, in plain words.
        updated_by: Which agent is updating it.
    """
    try:
        return ops.update_ticket(ticket_id, status, note, updated_by)
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


# ==========================================================================
# Human-only tools
#
# These exist for the dashboard, not for the agents. `backend/mcp_client.py`
# filters both out of the toolset the agents receive — see HUMAN_ONLY_TOOLS.
# An agent that could approve its own request would make the approval rule
# decorative, and an agent that could reset the database could erase the
# evidence of what it did.
# ==========================================================================

HUMAN_ONLY_TOOLS = {"decide_approval", "reset_working_database"}


@server.tool(
    name="decide_approval",
    title="Record a human's approve/reject decision",
    description=(
        "HUMAN ONLY — for the dashboard. Records a person's decision on a "
        "pending approval. Agents must not call this; approving your own "
        "request defeats the point of the approval."
    ),
)
def decide_approval(
    approval_id: int, decision: str, decided_by: str, note: str = ""
) -> dict[str, Any]:
    """Approve or reject a pending request.

    Args:
        approval_id: Which approval.
        decision: "approved" or "rejected".
        decided_by: The person deciding. Recorded against any resulting payment.
        note: Optional reason, kept with the decision.
    """
    try:
        return ops.decide_approval(approval_id, decision, decided_by, note)
    except ops.RuleViolation as exc:
        raise ToolError(str(exc)) from exc


@server.tool(
    name="get_approval",
    title="Read one approval",
    description="One approval with its current status and decision, if any.",
)
def get_approval(approval_id: int) -> dict[str, Any]:
    """Look up a single approval.

    Args:
        approval_id: Which approval.
    """
    rows = ops.list_approvals()
    for row in rows:
        if row["id"] == approval_id:
            return row
    raise ToolError(f"No approval #{approval_id}.")


@server.tool(
    name="reset_working_database",
    title="Restore the working copy from the original",
    description=(
        "HUMAN ONLY — for the dashboard. Replaces campus_customs_new.db with "
        "a fresh copy of the untouched campus_customs.db and re-creates the "
        "agent tables, so a run can start over. The original is only read."
    ),
)
def reset_working_database() -> dict[str, Any]:
    """Start over from the supplied data.

    The file copy happens here rather than in the backend so that every
    database operation stays inside the MCP server.
    """
    import shutil

    source = db.DB_PATH.parent / "campus_customs.db"
    if not source.exists():
        raise ToolError(f"The original database is missing at {source}.")

    shutil.copy2(source, db.DB_PATH)
    with db.connect() as conn:
        ensure_schema(conn)
        counts = {
            t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            for t in ("tickets", "approvals", "drafts", "purchase_orders", "payments")
        }
        balance = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name='checking'"
        ).fetchone()["balance"]

    return {
        "reset": True,
        "restored_from": source.name,
        "row_counts": counts,
        "checking_balance": float(balance),
        "shop_date": db.today().isoformat(),
        "message": (
            "Working database restored from the original. Approvals, drafts "
            "and purchase orders cleared; cash and invoices back to their "
            "starting values."
        ),
    }


if __name__ == "__main__":
    server.run(transport="stdio")
