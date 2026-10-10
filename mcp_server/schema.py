"""Extra tables the agents need, added to the working copy only.

The supplied database has nowhere to put a pending approval, a drafted email,
or a purchase order — but the business rules require all three:

    "can't make payments without human approval"   -> approvals
    "emails and vendor messages are drafts only"   -> drafts
    "can't order from vendors with unpaid invoices" -> purchase_orders

So three tables are added to `campus_customs_new.db`. The nine supplied tables
are never altered, and `campus_customs.db` is never touched at all.

`ensure_schema()` is idempotent — it runs on server start and does nothing if
the tables already exist.
"""

from __future__ import annotations

import sqlite3

# Every write an agent makes lands in one of these, so the dashboard has a
# single place to look and nothing happens invisibly.
DDL = [
    # A request for a human to approve money leaving the shop, or a price
    # being changed. Nothing is paid or applied until status = 'approved'.
    """
    CREATE TABLE IF NOT EXISTS approvals (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        kind          TEXT NOT NULL,      -- invoice_payment | rent_payment | purchase_order | price_override
        ref_id        INTEGER,            -- invoice id, lease id, vendor id, or ticket id
        ticket_id     INTEGER,
        amount        REAL NOT NULL,
        requested_by  TEXT NOT NULL,      -- which agent asked
        reason        TEXT NOT NULL,      -- why, in plain words, for the human reading it
        details_json  TEXT,               -- structured extras (sku, size, qty, proposed price)
        status        TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
        created_at    TEXT NOT NULL,
        decided_at    TEXT,
        decided_by    TEXT,
        decision_note TEXT
    )
    """,
    # Customer emails and vendor messages. Written here and never sent.
    """
    CREATE TABLE IF NOT EXISTS drafts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        kind        TEXT NOT NULL,        -- customer_email | vendor_message
        ticket_id   INTEGER,
        recipient   TEXT NOT NULL,
        subject     TEXT NOT NULL,
        body        TEXT NOT NULL,
        created_by  TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'draft'   -- always 'draft'; nothing sends these
    )
    """,
    # A restock order. Only created once an approval exists and the vendor
    # has no unpaid invoices.
    """
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id    INTEGER NOT NULL,
        ticket_id    INTEGER,
        sku          TEXT NOT NULL,
        size         TEXT,
        qty          INTEGER NOT NULL,
        unit_cost    REAL NOT NULL,
        total_cost   REAL NOT NULL,
        approval_id  INTEGER NOT NULL,
        status       TEXT NOT NULL DEFAULT 'placed',
        created_by   TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        expected_days INTEGER,
        FOREIGN KEY (vendor_id)   REFERENCES vendors(id),
        FOREIGN KEY (approval_id) REFERENCES approvals(id)
    )
    """,
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the agent tables if they are not there yet. Safe to call often."""
    for statement in DDL:
        conn.execute(statement)
    conn.commit()
