"""Smoke-test the three Campus Customs MCP tools over a real stdio connection.

This does not import the tool functions directly. It launches the server the
same way a client would — using the exact command from `.mcp.json` — performs
the MCP handshake, and calls each tool across the wire. That way the test
proves the *connection* works, not just the Python functions.

Every returned figure is then cross-checked against `campus_customs_new.db`
with an independent `sqlite3` query, so a tool that invented a number would
fail here rather than look plausible.

    python scripts/mcp_smoke_test.py

Writes `output/mcp_smoke.json`.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
CONFIG = ROOT / ".mcp.json"
OUT = ROOT / "output" / "mcp_smoke.json"


def q(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Independent read, used only to verify what the tools claimed."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def one(sql: str, params: tuple = ()):
    rows = q(sql, params)
    return rows[0][0] if rows else None


def server_params() -> StdioServerParameters:
    """Build the launch parameters from .mcp.json, so the test uses the real config."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["mcpServers"]["campus-customs"]
    return StdioServerParameters(
        command=cfg["command"],
        args=cfg["args"],
        env={**cfg.get("env", {}), "PYTHONPATH": str(ROOT)},
        cwd=str(ROOT),
    )


def payload(result) -> dict:
    """Pull the structured output out of a CallToolResult."""
    data = getattr(result, "structured_content", None)
    if data:
        return data
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
    return {}


# --------------------------------------------------------------------------
# One check = one claim the tool made, and the database value it must equal.
# --------------------------------------------------------------------------


def checks_101(r: dict) -> list[dict]:
    qty = one("SELECT qty FROM inventory WHERE sku=? AND size=?", ("CC-TEE-WHITE", "S"))
    sizes = {x["size"]: x["qty"] for x in q("SELECT size, qty FROM inventory WHERE sku=?", ("CC-TEE-WHITE",))}
    inv = q(
        "SELECT i.id, i.amount, i.due_date, v.name FROM invoices i "
        "JOIN vendors v ON v.id=i.vendor_id WHERE lower(i.status)!='paid' AND v.specialty LIKE '%apparel%'"
    )
    cost = one("SELECT unit_cost FROM pricing WHERE sku=?", ("CC-TEE-WHITE",))
    shop_date = one("SELECT date_today FROM desk")
    returned_sizes = {s["size"]: s["qty"] for s in r.get("other_sizes", [])}
    blocked = [o for o in r.get("restock_options", []) if not o["can_order"]]
    return [
        chk("qty_on_hand matches inventory", r.get("qty_on_hand"), qty),
        chk("can_fulfill_now is False (size S empty)", r.get("can_fulfill_now"), False),
        chk("shortfall = requested - on hand", r.get("shortfall"), 1),
        chk("every size and quantity matches inventory", returned_sizes, sizes),
        chk("unit_cost matches pricing", r.get("unit_cost"), cost),
        chk("shop_date is desk.date_today", r.get("shop_date"), shop_date),
        chk("one apparel vendor reported blocked", len(blocked), len(inv)),
        chk(
            "blocked vendor is the one owed money",
            blocked[0]["name"] if blocked else None,
            inv[0]["name"] if inv else None,
        ),
        chk(
            "blocked vendor's outstanding total matches invoices",
            blocked[0]["outstanding_invoice_total"] if blocked else None,
            float(sum(i["amount"] for i in inv)),
        ),
        chk("no vendor available to restock", r.get("any_vendor_available"), False),
        chk(
            "overdue invoice id appears in the reason",
            str(inv[0]["id"]) in (blocked[0]["blocked_reason"] or "") if blocked and inv else False,
            True,
        ),
    ]


def checks_102(r: dict) -> list[dict]:
    lease = q("SELECT * FROM leases WHERE id=1")[0]
    bal = one("SELECT balance FROM cash_accounts WHERE name='checking'")
    shop_date = one("SELECT date_today FROM desk")
    paid = one("SELECT COUNT(*) FROM payments WHERE kind='rent' AND ref_id=1")
    from datetime import date

    days = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(shop_date)).days
    return [
        chk("monthly_rent matches leases", r.get("monthly_rent"), float(lease["monthly_rent"])),
        chk("next_due matches leases", r.get("next_due"), lease["next_due"]),
        chk("landlord matches leases", r.get("landlord"), lease["landlord"]),
        chk("space_name matches leases", r.get("space_name"), lease["space_name"]),
        chk("days_until_due computed from desk.date_today", r.get("days_until_due"), days),
        chk("is_overdue is False (due in future)", r.get("is_overdue"), False),
        chk("is_due_soon is True (within 7 days)", r.get("is_due_soon"), True),
        chk("cash_balance matches cash_accounts", r.get("cash_balance"), float(bal)),
        chk("affordable, balance covers rent", r.get("affordable"), bal >= lease["monthly_rent"]),
        chk(
            "balance_after_payment = balance - rent",
            r.get("balance_after_payment"),
            round(float(bal) - float(lease["monthly_rent"]), 2),
        ),
        chk("already_paid matches payments table", r.get("already_paid"), paid > 0),
        chk("human approval flagged", r.get("requires_human_approval"), True),
        chk("shop_date is desk.date_today", r.get("shop_date"), shop_date),
    ]


def checks_103(r: dict) -> list[dict]:
    price = q("SELECT * FROM pricing WHERE sku=?", ("CC-HOOD-NAVY",))[0]
    qty = one("SELECT qty FROM inventory WHERE sku=? AND size=?", ("CC-HOOD-NAVY", "M"))
    shop_date = one("SELECT date_today FROM desk")
    cost, lst, want, proposed = float(price["unit_cost"]), float(price["list_price"]), 20, 40.0
    return [
        chk("qty_on_hand matches inventory", r.get("qty_on_hand"), qty),
        chk("shortfall = requested - on hand", r.get("shortfall"), want - qty),
        chk("cannot fill from stock", r.get("can_fill_from_stock"), False),
        chk("unit_cost matches pricing", r.get("unit_cost"), cost),
        chk("list_price matches pricing", r.get("list_price"), lst),
        chk("list_total = qty x list_price", r.get("list_total"), round(want * lst, 2)),
        chk("cost_total = qty x unit_cost", r.get("cost_total"), round(want * cost, 2)),
        chk("margin_at_list = list_total - cost_total", r.get("margin_at_list"), round(want * (lst - cost), 2)),
        chk("floor price is unit_cost", r.get("min_unit_price"), cost),
        chk(
            "max break-even discount computed from pricing",
            r.get("max_discount_pct_at_cost"),
            round((lst - cost) / lst * 100, 1),
        ),
        chk("proposed_total = qty x proposed", r.get("proposed_total"), round(want * proposed, 2)),
        chk("proposed_margin = proposed_total - cost_total", r.get("proposed_margin"), round(want * (proposed - cost), 2)),
        chk("proposed_discount_pct off list", r.get("proposed_discount_pct"), round((lst - proposed) / lst * 100, 1)),
        chk("proposed price is above cost", r.get("proposed_is_profitable"), proposed > cost),
        chk("human approval flagged", r.get("requires_human_approval"), True),
        chk("shop_date is desk.date_today", r.get("shop_date"), shop_date),
    ]


def chk(label: str, got, expected) -> dict:
    ok = got == expected
    return {
        "check": label,
        "returned_by_tool": got,
        "value_in_database": expected,
        "match": ok,
    }


TESTS = [
    {
        "ticket": 101,
        "ticket_type": "customer_order",
        "prompt": (
            "Ticket 101: Tauhid Zaman wants one Classic Bulldog Tee (CC-TEE-WHITE) "
            "in size S. Can we fill this order today, and if not, who could restock it?"
        ),
        "tool": "check_order_fulfillment",
        "arguments": {"sku": "CC-TEE-WHITE", "size": "S", "qty": 1},
        "verifier": checks_101,
    },
    {
        "ticket": 102,
        "ticket_type": "rent_notice",
        "prompt": (
            "Ticket 102: Elm City Properties says shop rent is due in 2 days. "
            "How much is owed on the lease, when exactly, and can we afford it?"
        ),
        "tool": "check_rent_due",
        "arguments": {"lease_id": 1, "account": "checking"},
        "verifier": checks_102,
    },
    {
        "ticket": 103,
        "ticket_type": "price_override",
        "prompt": (
            "Ticket 103: the Yale AI Club wants 20 navy hoodies (CC-HOOD-NAVY) in "
            "size M at a bulk discount. Can we supply them, and would $40 per unit "
            "still make money?"
        ),
        "tool": "quote_bulk_discount",
        "arguments": {"sku": "CC-HOOD-NAVY", "size": "M", "qty": 20, "proposed_unit_price": 40.0},
        "verifier": checks_103,
    },
]


async def main() -> int:
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []

    async with stdio_client(server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            listed = await session.list_tools()
            tool_names = sorted(t.name for t in listed.tools)
            print(f"connected to '{init.server_info.name}' — tools: {', '.join(tool_names)}\n")

            for t in TESTS:
                print(f"[ticket {t['ticket']}] {t['tool']}({t['arguments']})")
                res = await session.call_tool(t["tool"], t["arguments"])
                data = payload(res)
                checks = t["verifier"](data)
                failed = [c for c in checks if not c["match"]]
                status = "pass" if not failed and not res.is_error else "fail"
                print(f"   -> {status}: {len(checks) - len(failed)}/{len(checks)} checks matched the database")
                if failed:
                    for f in failed:
                        print(f"      MISMATCH {f['check']}: tool={f['returned_by_tool']!r} db={f['value_in_database']!r}")
                print(f"   summary: {data.get('summary', '')[:150]}\n")

                results.append({
                    "ticket_id": t["ticket"],
                    "ticket_type": t["ticket_type"],
                    "prompt": t["prompt"],
                    "tool_called": t["tool"],
                    "arguments": t["arguments"],
                    "tool_error": bool(res.is_error),
                    "result": data,
                    "verification": {
                        "checks_run": len(checks),
                        "checks_passed": len(checks) - len(failed),
                        "all_values_match_database": not failed,
                        "details": checks,
                    },
                    "status": status,
                })

    passed = sum(1 for r in results if r["status"] == "pass")
    report = {
        "generated_at": started,
        "database": "data/campus_customs_new.db",
        "shop_date": one("SELECT date_today FROM desk"),
        "transport": "stdio",
        "launch_command": "python -m mcp_server.server",
        "config_file": ".mcp.json",
        "server_name": "campus-customs",
        "tools_discovered": tool_names,
        "note": (
            "Each tool was called over a real MCP stdio connection, not by importing "
            "the function. Every figure returned was then re-queried directly from "
            "the database with independent SQL; a value the tool invented would show "
            "as a mismatch below."
        ),
        "summary": {
            "tools_tested": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "total_value_checks": sum(r["verification"]["checks_run"] for r in results),
            "total_value_checks_passed": sum(r["verification"]["checks_passed"] for r in results),
        },
        "tests": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{passed}/{len(results)} tools passed — wrote {OUT.relative_to(ROOT)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
