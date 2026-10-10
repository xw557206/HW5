"""Exercise every backend route without running agents or moving real money.

Uses FastAPI's in-process test client, so no server is needed. `POST
/tickets/{id}/run` is tested only for its guard rails — a bad ticket id — so
no model call is ever made.

The approval route *is* tested end to end, because that is where money moves
and the rules matter most. It uses approvals created directly against the
MCP server, and the database is reset afterwards.

    python scripts/api_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

results: list[tuple[bool, str, str]] = []


def check(label: str, got, expected) -> None:
    ok = got == expected
    results.append((ok, label, "" if ok else f"got {got!r}, expected {expected!r}"))
    print(f"   {'ok  ' if ok else 'FAIL'}  {label}" + ("" if ok else f"  -> {got!r} != {expected!r}"))


def section(n: str) -> None:
    print(f"\n{'=' * 74}\n{n}\n{'=' * 74}")


def main() -> int:
    with TestClient(app) as c:
        # Start from a known state.
        c.post("/reset")

        # ---------------------------------------------------------------
        section("GET /health")
        r = c.get("/health").json()
        check("ok", r["ok"], True)
        check("MCP connected", r["mcp_connected"], True)
        check("all 19 tools reachable", r["mcp_tools"], 19)
        check("shop date from the database", r["shop_date"], "2026-08-31")

        # ---------------------------------------------------------------
        section("GET /tickets")
        r = c.get("/tickets")
        check("HTTP 200", r.status_code, 200)
        d = r.json()
        check("three tickets", d["count"], 3)
        check("ids", [t["id"] for t in d["tickets"]], [101, 102, 103])
        check("all open", all(t["is_open"] for t in d["tickets"]), True)
        check("101 description present", d["tickets"][0]["description"], "Needs a tee in size S.")
        check("102 links its lease", d["tickets"][1]["lease_id"], 1)
        check("101 links its invoice", d["tickets"][0]["invoice_id"], 501)
        for t in d["tickets"]:
            print(f"      #{t['id']} {t['type']:<15} {t['status']:<6} {t['subject']}")

        # ---------------------------------------------------------------
        section("GET /cash")
        r = c.get("/cash").json()
        check("balance from cash_accounts", r["balance"], 3400.0)
        check("nothing committed yet", r["committed_by_open_requests"], 0.0)
        check("available equals balance", r["available_to_commit"], 3400.0)

        # ---------------------------------------------------------------
        section("POST /tickets/{id}/run — guard rails only (no model calls)")
        r = c.post("/tickets/999/run")
        check("unknown ticket is 404", r.status_code, 404)
        check("error names the real tickets", "101, 102 and 103" in r.json()["detail"], True)
        print(f"      {r.json()['detail']}")

        # ---------------------------------------------------------------
        section("GET /events")
        r = c.get("/events?limit=5").json()
        check("ok", r["ok"], True)
        check("events list returned", isinstance(r["events"], list), True)
        print(f"      {r['total_recorded']} entries recorded, {r['count']} returned")

        # ---------------------------------------------------------------
        section("POST /approvals/{id} — rejection must not move money")
        a = mcp_request(c, "invoice_payment", 840.0, 501, 101, "Invoice 501 is 3 days overdue")
        before = c.get("/cash").json()["balance"]
        r = c.post(f"/approvals/{a}", json={"decision": "rejected", "decided_by": "owner",
                                            "note": "not this week"}).json()
        after = c.get("/cash").json()["balance"]
        check("status rejected", r["status"], "rejected")
        check("nothing executed", r["executed"], False)
        check("balance unchanged", after, before)
        print(f"      {r['message']}")

        # ---------------------------------------------------------------
        section("POST /approvals/{id} — cannot decide the same request twice")
        r = c.post(f"/approvals/{a}", json={"decision": "approved", "decided_by": "owner"})
        check("HTTP 409", r.status_code, 409)
        check("explains it was already decided", "already rejected" in r.json()["detail"], True)
        print(f"      {r.json()['detail']}")

        # ---------------------------------------------------------------
        section("POST /approvals/{id} — missing request")
        r = c.post("/approvals/4242", json={"decision": "approved", "decided_by": "owner"})
        check("HTTP 404", r.status_code, 404)
        print(f"      {r.json()['detail']}")

        # ---------------------------------------------------------------
        section("POST /approvals/{id} — insufficient cash is blocked even when approved")
        big = mcp_request(c, "rent_payment", 999999.0, 1, 102, "Deliberately unaffordable",
                          skip_cash_guard=True)
        if big is None:
            print("      (the request tool refused it up front, which is also correct)")
            check("unaffordable request refused at request time", True, True)
        else:
            before = c.get("/cash").json()["balance"]
            r = c.post(f"/approvals/{big}", json={"decision": "approved",
                                                  "decided_by": "owner"}).json()
            after = c.get("/cash").json()["balance"]
            check("blocked", r["status"], "blocked")
            check("not executed", r["executed"], False)
            check("balance unchanged", after, before)
            print(f"      {r['message']}")

        # ---------------------------------------------------------------
        section("POST /approvals/{id} — approving a payment moves money exactly once")
        a2 = mcp_request(c, "invoice_payment", 840.0, 501, 101, "Settle 501 to unblock the vendor")
        before = c.get("/cash").json()["balance"]
        r = c.post(f"/approvals/{a2}", json={"decision": "approved",
                                             "decided_by": "owner"}).json()
        after = c.get("/cash").json()["balance"]
        check("executed", r["status"], "executed")
        check("payment recorded", r["executed"], True)
        check("balance reduced by the amount", round(before - after, 2), 840.0)
        check("new balance reported", r["new_balance"], 2560.0)
        print(f"      {r['message']}")

        r2 = c.post(f"/approvals/{a2}", json={"decision": "approved", "decided_by": "owner"})
        check("second attempt refused (no double payment)", r2.status_code, 409)
        print(f"      {r2.json()['detail']}")

        # ---------------------------------------------------------------
        section("POST /approvals/{id} — vendor restrictions still apply on execution")
        c.post("/reset")  # invoice 501 unpaid again, so vendor 1 is blocked
        po = mcp_request(c, "purchase_order", 264.0, 1, 103,
                         "Restock 12 navy hoodies in M",
                         details={"vendor_id": 1, "sku": "CC-HOOD-NAVY", "qty": 12, "size": "M"})
        r = c.post(f"/approvals/{po}", json={"decision": "approved",
                                             "decided_by": "owner"}).json()
        check("blocked despite human approval", r["status"], "blocked")
        check("no purchase order created", r["purchase_order_id"], None)
        check("reason names the unpaid invoice", "unpaid invoice" in r["message"], True)
        print(f"      {r['message']}")

        # ---------------------------------------------------------------
        section("POST /reset")
        c.post("/approvals/" + str(mcp_request(c, "rent_payment", 2400.0, 1, 102, "rent")),
               json={"decision": "approved", "decided_by": "owner"})
        spent = c.get("/cash").json()["balance"]
        r = c.post("/reset").json()
        restored = c.get("/cash").json()
        check("reset reported", r["reset"], True)
        check("balance restored to 3400", restored["balance"], 3400.0)
        check("approvals cleared", r["row_counts"]["approvals"], 0)
        check("payments cleared", r["row_counts"]["payments"], 0)
        check("tickets intact", r["row_counts"]["tickets"], 3)
        check("audit trail kept by default", r["audit_entries_archived"], 0)
        print(f"      balance {spent} -> {restored['balance']}; {r['message']}")

    # -------------------------------------------------------------------
    print(f"\n{'=' * 74}")
    failed = [r for r in results if not r[0]]
    for ok, label, detail in results:
        if not ok:
            print(f"  FAIL  {label}: {detail}")
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    print("=" * 74)
    return 1 if failed else 0


def mcp_request(client, kind, amount, ref_id, ticket_id, reason, details=None,
                skip_cash_guard=False):
    """Seed an approval for a test, as an agent's `request_approval` would.

    Calls `mcp_server.ops` directly rather than going through the app's MCP
    connection. That connection belongs to the TestClient's event loop, and
    reaching into it from here deadlocks.

    This is test *setup* only — the routes under test still go through MCP.
    """
    from mcp_server import ops

    try:
        return ops.request_approval(
            kind=kind, amount=amount, requested_by="test-harness", reason=reason,
            ref_id=ref_id, ticket_id=ticket_id, details=details,
        )["approval_id"]
    except ops.RuleViolation:
        if skip_cash_guard:
            return None
        raise


if __name__ == "__main__":
    sys.exit(main())
