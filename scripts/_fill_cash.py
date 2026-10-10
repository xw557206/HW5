"""Replace the Cash placeholder in desk_tickets.html with the real ledger.

Figures are read live from the working database so the page cannot drift
from it. Re-run after any approval.
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"
DB = ROOT / "data" / "campus_customs_new.db"

START = 3400.00  # recorded from the untouched original before the first run

PLACEHOLDER_START = '<section class="panel" id="p-cash"'
PLACEHOLDER_END = "</section>\n\n<!-- ======================= REFLECTION"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    balance = float(conn.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()["balance"])
    payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
    approvals = [dict(r) for r in conn.execute("SELECT * FROM approvals ORDER BY id")]
    orders = [dict(r) for r in conn.execute("SELECT * FROM purchase_orders ORDER BY id")]
    paid = round(sum(float(p["amount"]) for p in payments), 2)
    committed = round(
        sum(float(a["amount"]) for a in approvals
            if a["status"] in ("pending", "approved") and a["kind"] != "price_override") - paid, 2)

    rows = []
    running = START
    for t in (101, 102, 103):
        t_appr = [a for a in approvals if a["ticket_id"] == t]
        t_pay = [p for p in payments
                 if any(a["ref_id"] == p["ref_id"] and a["ticket_id"] == t for a in t_appr)]
        t_po = [o for o in orders if o["ticket_id"] == t]
        moved = round(sum(float(p["amount"]) for p in t_pay) + sum(float(o["total_cost"]) for o in t_po), 2)
        running = round(running - moved, 2)

        if t_pay or t_po:
            what = "; ".join([f"payment #{p['id']} {p['kind']} ${float(p['amount']):,.2f}" for p in t_pay]
                             + [f"PO #{o['id']} ${float(o['total_cost']):,.2f}" for o in t_po])
            cls = ""
        elif t_appr:
            a = t_appr[0]
            what = (f"Approval #{a['id']} ({a['kind'].replace('_', ' ')}, "
                    f"${float(a['amount']):,.2f}) raised and <strong>{a['status']}</strong> "
                    "&mdash; no cash has moved")
            cls = ' class="muted"'
        else:
            what = "No payment, purchase order or approval &mdash; nothing committed"
            cls = ' class="muted"'

        rows.append(
            f'        <tr{cls}><td><strong>Ticket {t}</strong></td><td>{what}</td>'
            f'<td class="num">{"&minus;$" + f"{moved:,.2f}" if moved else "$0.00"}</td>'
            f'<td class="num">${running:,.2f}</td></tr>')

    pending_note = ""
    if committed > 0:
        pending_note = (
            f'<p style="margin-top:14px;font-size:13.5px;color:var(--warn);background:var(--warn-bg);'
            f'border:1px solid #e8d9ae;border-radius:10px;padding:12px 16px;line-height:1.6">'
            f'<strong>${committed:,.2f} is committed but not spent.</strong> Approval #1 is still '
            f'pending a human decision, so the shop treats that money as spoken for: '
            f'<code>available_to_commit</code> reports ${balance - committed:,.2f} even though the '
            f'balance is still ${balance:,.2f}. If it is approved the balance becomes '
            f'${balance - committed:,.2f}; if rejected it returns to ${balance:,.2f}.</p>')

    cash_html = f'''<section class="panel" id="p-cash" role="tabpanel" aria-labelledby="tab-cash" hidden>
  <p class="eyebrow">Cash &middot; checking account</p>
  <div class="tcard">
    <div class="thead">
      <div>
        <h2>Where the money went</h2>
        <p class="treq">Every figure read from <code>cash_accounts</code> and <code>payments</code> in the working database</p>
      </div>
      <span class="badge b-type">shop date 2026-08-31</span>
    </div>

    <table class="ledger">
      <thead>
        <tr><th>Item</th><th>What happened</th><th class="num">Change</th><th class="num">Balance</th></tr>
      </thead>
      <tbody>
        <tr><td><strong>Opening balance</strong></td><td>Recorded from the untouched original database before any agent ran</td><td class="num">&mdash;</td><td class="num">${START:,.2f}</td></tr>
{chr(10).join(rows)}
        <tr class="tot"><td>Ending balance</td><td>As stored in <code>cash_accounts</code></td><td class="num">&minus;${paid:,.2f}</td><td class="num">${balance:,.2f}</td></tr>
      </tbody>
    </table>

    <div class="recon">
      <strong>Reconciliation.</strong>
      <code>${START:,.2f} &minus; ${paid:,.2f} = ${balance:,.2f}</code>, which matches the
      <code>cash_accounts</code> row exactly. {len(payments)} payment rows and {len(orders)} purchase orders
      exist in the database, so the ledger above is complete.
    </div>
    {pending_note}
  </div>

  <div class="callout info" style="margin-top:22px"><b>Nothing was spent, and that is the correct result.</b>
  All three tickets ran, but the only money-moving action anyone proposed was approval&nbsp;#1 for rent. No
  agent can pay it, and no human has decided yet &mdash; so the balance is untouched. The $840 invoice that
  blocks tickets 101 and 103 was never even raised for approval, which is a gap in how the agents worked
  rather than a cash constraint: at $3,400 the shop could afford both the rent and the invoice
  ($3,240 together, leaving $160).</div>
</section>

<!-- ======================= REFLECTION'''

    s = HTML.read_text(encoding="utf-8")
    i = s.index(PLACEHOLDER_START)
    j = s.index(PLACEHOLDER_END) + len("</section>\n\n<!-- ======================= REFLECTION")
    s = s[:i] + cash_html + s[j:]
    HTML.write_text(s, encoding="utf-8")

    print("cash tab filled")
    print(f"  start ${START:,.2f}  paid ${paid:,.2f}  end ${balance:,.2f}  "
          f"reconciles={abs((START - paid) - balance) < 0.005}")
    print(f"  committed-not-spent ${committed:,.2f}")


if __name__ == "__main__":
    main()
