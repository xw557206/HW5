"""Database access for the Campus Customs MCP server.

Every value the tools return comes from here, so there is exactly one place
where SQL lives and nothing can quietly invent a number.

Two rules this module exists to enforce:

1. **The working copy only.** All reads go to `data/campus_customs_new.db`.
   The supplied `data/campus_customs.db` is never opened.
2. **The shop's own date.** `today()` reads `desk.date_today`, never the
   system clock. The stored date is 2026-08-31; the real date is well past
   that, so using `date.today()` would make every overdue check wrong.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

# mcp_server/ -> project root -> data/
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"

# Anything that is not settled counts as outstanding. `invoices.status` is
# free text, so matching only the literal 'open' would miss states like
# 'overdue' or 'disputed' if they ever appear.
PAID = "paid"


def connect() -> sqlite3.Connection:
    """Open the working copy with row access by column name."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Working database not found at {DB_PATH}. "
            "Copy data/campus_customs.db to data/campus_customs_new.db first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def today() -> date:
    """The shop's current date, from `desk.date_today`.

    Not the system clock — see the module docstring.
    """
    with connect() as conn:
        row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("The desk table has no row, so the shop date is unknown.")
    return date.fromisoformat(row["date_today"])


def days_until(iso_date: str) -> int:
    """Days from the shop's date to `iso_date`. Negative means overdue."""
    return (date.fromisoformat(iso_date) - today()).days


# --------------------------------------------------------------------------
# Inventory and pricing
# --------------------------------------------------------------------------


def stock_for(sku: str, size: str) -> sqlite3.Row | None:
    """One inventory row, or None when that sku/size is not carried.

    A row can exist with `qty = 0`, so callers must read the quantity rather
    than treat "a row came back" as "we have stock".
    """
    with connect() as conn:
        return conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory "
            "WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()


def all_sizes_for(sku: str) -> list[sqlite3.Row]:
    """Every size carried for a sku, with quantities."""
    with connect() as conn:
        return conn.execute(
            "SELECT size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
            (sku,),
        ).fetchall()


def pricing_for(sku: str) -> sqlite3.Row | None:
    """Unit cost and list price for a sku."""
    with connect() as conn:
        return conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()


def product_name(sku: str) -> str | None:
    """The display name for a sku, taken from any inventory row."""
    with connect() as conn:
        row = conn.execute(
            "SELECT name FROM inventory WHERE sku = ? LIMIT 1", (sku,)
        ).fetchone()
    return row["name"] if row else None


# --------------------------------------------------------------------------
# Vendors and invoices
# --------------------------------------------------------------------------


def vendors() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"
        ).fetchall()


def outstanding_invoices(vendor_id: int | None = None) -> list[sqlite3.Row]:
    """Invoices that are not yet paid, newest due date first.

    Pass `vendor_id` to check one vendor's standing.
    """
    sql = (
        "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, "
        "       i.status, i.description "
        "FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
        "WHERE lower(i.status) != ?"
    )
    params: list[object] = [PAID]
    if vendor_id is not None:
        sql += " AND i.vendor_id = ?"
        params.append(vendor_id)
    sql += " ORDER BY i.due_date"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def invoice(invoice_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT i.id, i.vendor_id, v.name AS vendor_name, v.specialty, "
            "       v.lead_days, i.amount, i.due_date, i.status, i.description "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (invoice_id,),
        ).fetchone()


# --------------------------------------------------------------------------
# Leases, cash and payments
# --------------------------------------------------------------------------


def lease(lease_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()


def leases() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases ORDER BY next_due"
        ).fetchall()


def cash_balance(account: str = "checking") -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()


def payments_for(kind: str, ref_id: int) -> list[sqlite3.Row]:
    """Payments already recorded against an invoice or a lease.

    Lets a tool say "this has already been paid" instead of proposing a
    duplicate.
    """
    with connect() as conn:
        return conn.execute(
            "SELECT id, kind, ref_id, amount, account, paid_at, approved_by "
            "FROM payments WHERE kind = ? AND ref_id = ? ORDER BY paid_at",
            (kind, ref_id),
        ).fetchall()


def committed_cash() -> float:
    """Total already paid out, summed from the payments table."""
    with connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM payments").fetchone()
    return float(row["total"])


# --------------------------------------------------------------------------
# Tickets
# --------------------------------------------------------------------------


def ticket(ticket_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def open_tickets() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM tickets WHERE lower(status) = 'open' ORDER BY id"
        ).fetchall()
