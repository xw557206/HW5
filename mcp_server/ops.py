"""Write operations, with the shop's business rules enforced here in code.

Every rule in the assignment is checked in this module, not left to the
prompt. A prompt rule is a request to a language model; a check here is a
guarantee. If an agent is confused, jailbroken, or simply wrong, these
functions still refuse.

    no payment without human approval  -> record_payment() requires an
                                          approvals row with status='approved'
    no ordering from blocked vendors   -> create_purchase_order() re-checks
                                          unpaid invoices at order time
    never spend more than the cash     -> both money paths check the balance
                                          minus what is already committed
    the shop's own date                -> every timestamp uses desk.date_today
    comms are drafts only              -> drafts are the only output; there is
                                          no send function anywhere
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import db


class RuleViolation(Exception):
    """A business rule said no. The message is written for an agent to read."""


def _now() -> str:
    """A timestamp on the shop's clock, not the real one."""
    return f"{db.today().isoformat()}T00:00:00"


# --------------------------------------------------------------------------
# Cash
# --------------------------------------------------------------------------


def cash_position(account: str = "checking") -> dict[str, Any]:
    """Balance, what is already committed, and what is genuinely spendable.

    "Committed" matters: an approved-but-unpaid request is money that is
    effectively spoken for. Treating the raw balance as available is how two
    agents both approve spending the same dollars.
    """
    row = db.cash_balance(account)
    if row is None:
        raise RuleViolation(f"No cash account named '{account}'.")
    balance = float(row["balance"])

    with db.connect() as conn:
        pending = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS t FROM approvals "
            "WHERE status IN ('pending','approved') AND kind != 'price_override'"
        ).fetchone()["t"]

    committed = float(pending)
    return {
        "account": row["name"],
        "balance": balance,
        "committed_by_open_requests": round(committed, 2),
        "available_to_commit": round(balance - committed, 2),
        "as_of": row["date"],
        "shop_date": db.today().isoformat(),
    }


def _assert_affordable(amount: float, account: str, what: str) -> None:
    pos = cash_position(account)
    if amount > pos["available_to_commit"]:
        raise RuleViolation(
            f"Cannot commit ${amount:,.2f} for {what}: only "
            f"${pos['available_to_commit']:,.2f} is available "
            f"(balance ${pos['balance']:,.2f} less ${pos['committed_by_open_requests']:,.2f} "
            "already committed to open requests). The shop may not spend more "
            "cash than it has."
        )


# --------------------------------------------------------------------------
# Approvals
# --------------------------------------------------------------------------

APPROVAL_KINDS = {"invoice_payment", "rent_payment", "purchase_order", "price_override"}


def request_approval(
    kind: str,
    amount: float,
    requested_by: str,
    reason: str,
    ref_id: int | None = None,
    ticket_id: int | None = None,
    details: dict[str, Any] | None = None,
    account: str = "checking",
) -> dict[str, Any]:
    """Create a pending approval for a human to decide on.

    This is the only route to spending money or changing a price. It does not
    spend anything itself — it asks.
    """
    if kind not in APPROVAL_KINDS:
        raise RuleViolation(
            f"'{kind}' is not an approval kind. Use one of: {', '.join(sorted(APPROVAL_KINDS))}."
        )
    if amount < 0:
        raise RuleViolation("An approval amount cannot be negative.")
    if not reason.strip():
        raise RuleViolation("An approval needs a reason — a human has to read it and decide.")

    # Price overrides do not move cash, so they are not checked against it.
    if kind != "price_override":
        _assert_affordable(amount, account, f"{kind} ({reason[:60]})")

    with db.connect() as conn:
        # Don't stack duplicate requests for the same thing.
        dup = conn.execute(
            "SELECT id FROM approvals WHERE kind=? AND ref_id IS ? AND status='pending'",
            (kind, ref_id),
        ).fetchone()
        if dup:
            raise RuleViolation(
                f"A pending {kind} request for ref {ref_id} already exists "
                f"(approval #{dup['id']}). Wait for the human decision rather "
                "than raising a second one."
            )
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, ticket_id, amount, requested_by, "
            "reason, details_json, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,'pending',?)",
            (kind, ref_id, ticket_id, float(amount), requested_by, reason.strip(),
             json.dumps(details) if details else None, _now()),
        )
        conn.commit()
        approval_id = cur.lastrowid

    return {
        "approval_id": approval_id,
        "kind": kind,
        "amount": float(amount),
        "status": "pending",
        "requires_human_approval": True,
        "message": (
            f"Approval #{approval_id} created and is waiting for a human. "
            f"Nothing has been paid or changed. A person must approve it on "
            "the dashboard first."
        ),
    }


def list_approvals(status: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM approvals"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id"
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def decide_approval(approval_id: int, decision: str, decided_by: str, note: str = "") -> dict[str, Any]:
    """Record a human's decision. Called by the dashboard, not by an agent."""
    if decision not in {"approved", "rejected"}:
        raise RuleViolation("A decision must be 'approved' or 'rejected'.")
    if not decided_by.strip():
        raise RuleViolation("A decision must record who made it.")

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            raise RuleViolation(f"No approval #{approval_id}.")
        if row["status"] != "pending":
            raise RuleViolation(
                f"Approval #{approval_id} was already {row['status']} — it cannot be decided twice."
            )
        conn.execute(
            "UPDATE approvals SET status=?, decided_at=?, decided_by=?, decision_note=? WHERE id=?",
            (decision, _now(), decided_by.strip(), note, approval_id),
        )
        conn.commit()
    return {"approval_id": approval_id, "status": decision, "decided_by": decided_by}


def _approved_or_refuse(conn: sqlite3.Connection, approval_id: int, expect_kind: set[str]) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if row is None:
        raise RuleViolation(f"No approval #{approval_id} exists. Request one first.")
    if row["status"] != "approved":
        raise RuleViolation(
            f"Approval #{approval_id} is '{row['status']}', not 'approved'. "
            "A human must approve it before this can go ahead."
        )
    if row["kind"] not in expect_kind:
        raise RuleViolation(
            f"Approval #{approval_id} is for '{row['kind']}', which does not "
            f"authorise this action (expected {', '.join(sorted(expect_kind))})."
        )
    return row


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------


def record_payment(approval_id: int, account: str = "checking") -> dict[str, Any]:
    """Pay something a human has approved, and move the cash.

    The approval is the authority. Without an approved row this refuses,
    which is the hard enforcement of "no payments without human approval".
    """
    with db.connect() as conn:
        appr = _approved_or_refuse(conn, approval_id, {"invoice_payment", "rent_payment"})

        already = conn.execute(
            "SELECT id FROM payments WHERE kind=? AND ref_id=?",
            ("invoice" if appr["kind"] == "invoice_payment" else "rent", appr["ref_id"]),
        ).fetchone()
        if already:
            raise RuleViolation(
                f"Already paid — payment #{already['id']} covers this. Not paying twice."
            )

        amount = float(appr["amount"])
        cash = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name=?", (account,)
        ).fetchone()
        if cash is None:
            raise RuleViolation(f"No cash account named '{account}'.")
        if amount > float(cash["balance"]):
            raise RuleViolation(
                f"Balance is ${float(cash['balance']):,.2f}; cannot pay ${amount:,.2f}."
            )

        kind = "invoice" if appr["kind"] == "invoice_payment" else "rent"
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?,?,?,?,?,?)",
            (kind, appr["ref_id"], amount, account, _now(), appr["decided_by"] or "unknown"),
        )
        payment_id = cur.lastrowid

        conn.execute(
            "UPDATE cash_accounts SET balance = balance - ? WHERE name = ?", (amount, account)
        )
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status='paid' WHERE id=?", (appr["ref_id"],))
        conn.commit()

        new_balance = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name=?", (account,)
        ).fetchone()["balance"]

    return {
        "payment_id": payment_id,
        "kind": kind,
        "ref_id": appr["ref_id"],
        "amount": amount,
        "account": account,
        "approved_by": appr["decided_by"],
        "new_balance": round(float(new_balance), 2),
        "message": (
            f"Paid ${amount:,.2f} ({kind} #{appr['ref_id']}), approved by "
            f"{appr['decided_by']}. Balance is now ${float(new_balance):,.2f}."
        ),
    }


# --------------------------------------------------------------------------
# Purchase orders
# --------------------------------------------------------------------------


def create_purchase_order(
    approval_id: int, vendor_id: int, sku: str, qty: int,
    created_by: str, size: str | None = None, ticket_id: int | None = None,
) -> dict[str, Any]:
    """Place a restock order — only when approved and the vendor is clear.

    The vendor's invoice standing is re-checked here, at order time, rather
    than trusted from whenever the agent last looked.
    """
    if qty <= 0:
        raise RuleViolation("A purchase order needs a positive quantity.")

    with db.connect() as conn:
        _approved_or_refuse(conn, approval_id, {"purchase_order"})

        vendor = conn.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
        if vendor is None:
            raise RuleViolation(f"No vendor with id {vendor_id}.")

        unpaid = conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id=? AND lower(status)!='paid'",
            (vendor_id,),
        ).fetchall()
        if unpaid:
            owed = sum(float(i["amount"]) for i in unpaid)
            refs = ", ".join(f"#{i['id']} ${float(i['amount']):,.2f}" for i in unpaid)
            raise RuleViolation(
                f"Cannot order from {vendor['name']}: {len(unpaid)} unpaid invoice(s) "
                f"totalling ${owed:,.2f} ({refs}). Settle the invoice before ordering."
            )

        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku=?", (sku,)).fetchone()
        if price is None:
            raise RuleViolation(f"No pricing row for {sku}, so the order cost is unknown.")
        unit_cost = float(price["unit_cost"])
        total = round(unit_cost * qty, 2)

        cur = conn.execute(
            "INSERT INTO purchase_orders (vendor_id, ticket_id, sku, size, qty, unit_cost, "
            "total_cost, approval_id, status, created_by, created_at, expected_days) "
            "VALUES (?,?,?,?,?,?,?,?,'placed',?,?,?)",
            (vendor_id, ticket_id, sku, size, qty, unit_cost, total, approval_id,
             created_by, _now(), vendor["lead_days"]),
        )
        conn.commit()
        po_id = cur.lastrowid

    return {
        "purchase_order_id": po_id,
        "vendor": vendor["name"],
        "sku": sku,
        "size": size,
        "qty": qty,
        "unit_cost": unit_cost,
        "total_cost": total,
        "expected_days": vendor["lead_days"],
        "message": (
            f"Purchase order #{po_id}: {qty} x {sku}"
            + (f" ({size})" if size else "")
            + f" from {vendor['name']} at ${unit_cost:,.2f}/unit, ${total:,.2f} total. "
            f"Expected in {vendor['lead_days']} day(s)."
        ),
    }


# --------------------------------------------------------------------------
# Drafts — written, never sent
# --------------------------------------------------------------------------


def save_draft(
    kind: str, recipient: str, subject: str, body: str, created_by: str,
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Save a customer email or vendor message as a draft.

    There is deliberately no send function anywhere in this codebase. The
    rule "communications are drafts only" is enforced by the absence of a
    way to do otherwise, not by asking the agent nicely.
    """
    if kind not in {"customer_email", "vendor_message"}:
        raise RuleViolation("Draft kind must be 'customer_email' or 'vendor_message'.")
    if not subject.strip() or not body.strip():
        raise RuleViolation("A draft needs both a subject and a body.")

    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO drafts (kind, ticket_id, recipient, subject, body, created_by, "
            "created_at, status) VALUES (?,?,?,?,?,?,?,'draft')",
            (kind, ticket_id, recipient, subject.strip(), body.strip(), created_by, _now()),
        )
        conn.commit()
        draft_id = cur.lastrowid

    return {
        "draft_id": draft_id,
        "kind": kind,
        "recipient": recipient,
        "subject": subject.strip(),
        "status": "draft",
        "sent": False,
        "message": (
            f"Draft #{draft_id} saved for {recipient}. It has NOT been sent — "
            "a person reviews and sends it."
        ),
    }


def list_drafts(ticket_id: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM drafts"
    params: list[Any] = []
    if ticket_id is not None:
        sql += " WHERE ticket_id = ?"
        params.append(ticket_id)
    sql += " ORDER BY id"
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


# --------------------------------------------------------------------------
# Tickets
# --------------------------------------------------------------------------

TICKET_STATUSES = {"open", "in_progress", "waiting_approval", "resolved", "blocked"}


def update_ticket(ticket_id: int, status: str, note: str, updated_by: str) -> dict[str, Any]:
    """Move a ticket along and append a note saying who did what and why."""
    if status not in TICKET_STATUSES:
        raise RuleViolation(
            f"'{status}' is not a ticket status. Use one of: {', '.join(sorted(TICKET_STATUSES))}."
        )
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if row is None:
            raise RuleViolation(f"No ticket #{ticket_id}.")
        # Append rather than replace, so the ticket keeps its history.
        existing = row["notes"] or ""
        stamped = f"{existing}\n[{_now()[:10]} {updated_by}] {note}".strip()
        conn.execute(
            "UPDATE tickets SET status=?, notes=? WHERE id=?", (status, stamped, ticket_id)
        )
        conn.commit()
    return {
        "ticket_id": ticket_id,
        "previous_status": row["status"],
        "status": status,
        "message": f"Ticket #{ticket_id} moved from '{row['status']}' to '{status}'.",
    }
