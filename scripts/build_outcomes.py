"""Build output/resolved_tickets.json from the real execution records.

Reads the working database and the audit trail — nothing is passed in by
hand, so the file cannot drift from what actually happened. Re-run it after
any further agent run or approval and the record updates.

    python scripts/build_outcomes.py
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
AUDIT = ROOT / "output" / "audit_trail.json"
OUT = ROOT / "output" / "resolved_tickets.json"

# Problem 5's wiring checks ran a TestModel against ticket ids. They stay in
# the audit file but are not shop work, so they are excluded here.
SCAFFOLD_RUNS = {"offline-check"}


def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else []
    real = [e for e in audit if e.get("run_id") not in SCAFFOLD_RUNS]
    failed = [e for e in real if e.get("status") == "error"]

    tickets = rows(conn, "SELECT * FROM tickets ORDER BY id")
    approvals = rows(conn, "SELECT * FROM approvals ORDER BY id")
    payments = rows(conn, "SELECT * FROM payments ORDER BY id")
    drafts = rows(conn, "SELECT * FROM drafts ORDER BY id")
    orders = rows(conn, "SELECT * FROM purchase_orders ORDER BY id")
    cash = dict(conn.execute("SELECT * FROM cash_accounts WHERE name='checking'").fetchone())
    shop_date = conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]

    out_tickets = []
    for t in tickets:
        tid = t["id"]
        entries = [e for e in real if e.get("ticket_id") == tid and e.get("status") == "ok"]
        # Oldest first, so the sequence reads in the order it happened.
        entries = list(reversed(entries)) if entries and entries[0].get("started_at", "") > entries[-1].get("started_at", "") else entries
        entries.sort(key=lambda e: (e.get("started_at", ""), e.get("delegation_depth", 0)))

        contributions = []
        for e in entries:
            contributions.append({
                "agent": e["agent"],
                "delegation_depth": e.get("delegation_depth", 0),
                "invoked_by": "orchestrator" if e.get("delegation_depth", 0) == 0
                              else "another agent",
                "tool_calls": e.get("iterations", 0),
                "tools_used": e.get("tools_used", []),
                "delegated_to": e.get("delegated_to", []),
                "rule_refusals": e.get("rule_refusals", []),
                "contribution": e.get("result_summary"),
            })

        t_approvals = [
            {
                "approval_id": a["id"], "kind": a["kind"], "amount": a["amount"],
                "requested_by": a["requested_by"], "reason": a["reason"],
                "status": a["status"], "decided_by": a["decided_by"],
                "decided_at": a["decided_at"], "decision_note": a["decision_note"],
                "executed": any(p["ref_id"] == a["ref_id"] for p in payments),
            }
            for a in approvals if a["ticket_id"] == tid
        ]
        t_payments = [p for p in payments
                      if any(a["ref_id"] == p["ref_id"] and a["ticket_id"] == tid for a in approvals)]
        t_drafts = [{"draft_id": d["id"], "kind": d["kind"], "recipient": d["recipient"],
                     "subject": d["subject"], "created_by": d["created_by"], "status": d["status"],
                     "sent": False} for d in drafts if d["ticket_id"] == tid]
        t_orders = [o for o in orders if o["ticket_id"] == tid]

        status = t["status"]
        out_tickets.append({
            "ticket_id": tid,
            "type": t["type"],
            "requester": t["requester"],
            "subject": t["subject"],
            "final_status": status,
            "is_resolved": status.lower() == "resolved",
            "outcome": (contributions[-1]["contribution"] if contributions
                        else "No successful agent run is recorded for this ticket."),
            "agents_involved": [c["agent"] for c in contributions],
            "agent_contributions": contributions,
            "human_approvals": t_approvals,
            "payments_made": t_payments,
            "drafts_written": t_drafts,
            "purchase_orders": t_orders,
            "cash_impact": round(sum(float(p["amount"]) for p in t_payments), 2),
            "blocked_by": _blocker(tid, status, t_approvals),
        })

    starting = 3400.0  # recorded before the first run; the untouched original
    spent = round(sum(float(p["amount"]) for p in payments), 2)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "shop_date": shop_date,
        "database": "data/campus_customs_new.db",
        "summary": {
            "tickets": len(out_tickets),
            "resolved": sum(1 for t in out_tickets if t["is_resolved"]),
            "awaiting_approval": sum(1 for t in out_tickets if t["final_status"] == "waiting_approval"),
            "blocked": sum(1 for t in out_tickets if t["final_status"] == "blocked"),
            "still_open": sum(1 for t in out_tickets if t["final_status"] == "open"),
            "approvals_raised": len(approvals),
            "approvals_pending": sum(1 for a in approvals if a["status"] == "pending"),
            "payments_made": len(payments),
            "drafts_written": len(drafts),
            "purchase_orders": len(orders),
            "failed_agent_runs": len(failed),
        },
        "cash": {
            "starting_balance": starting,
            "total_paid": spent,
            "ending_balance": float(cash["balance"]),
            "reconciles": abs((starting - spent) - float(cash["balance"])) < 0.005,
            "committed_to_pending_approvals": round(
                sum(float(a["amount"]) for a in approvals
                    if a["status"] in ("pending", "approved") and a["kind"] != "price_override")
                - spent, 2),
        },
        "tickets": out_tickets,
        "note": (
            "Built directly from campus_customs_new.db and output/audit_trail.json. "
            "A ticket is marked resolved only when the database says so."
        ),
    }

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    s = report["summary"]
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {s['tickets']} tickets: {s['resolved']} resolved, "
          f"{s['awaiting_approval']} awaiting approval, {s['blocked']} blocked, "
          f"{s['still_open']} still open")
    print(f"  approvals {s['approvals_raised']} ({s['approvals_pending']} pending), "
          f"payments {s['payments_made']}, drafts {s['drafts_written']}")
    c = report["cash"]
    print(f"  cash ${c['starting_balance']:,.2f} - ${c['total_paid']:,.2f} = "
          f"${c['ending_balance']:,.2f}  reconciles={c['reconciles']}")


def _blocker(tid, status, approvals):
    if status.lower() == "resolved":
        return None
    pending = [a for a in approvals if a["status"] == "pending"]
    if pending:
        return (f"Waiting on a human decision for approval #{pending[0]['approval_id']} "
                f"({pending[0]['kind']}, ${pending[0]['amount']:,.2f}).")
    return None  # the per-ticket narrative in the audit trail carries the detail


if __name__ == "__main__":
    main()
