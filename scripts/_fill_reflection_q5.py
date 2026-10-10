"""Replace Question 5 with the owner's own answer, and close the summary
with the lesson they drew.

Their wording, grammar tidied only. The "what is missing" boxes were checked
against the live schema and tool list: no refund tool, no sales history
table, no delivery tracking anywhere in the 19 tools or 12 tables.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

Q5_START = "  <!-- ============ Q5 ============ -->"
CLOSER_MARK = '<div class="q" style="border-left:4px solid var(--gold)">'

NEW_Q5 = '''  <!-- ============ Q5 ============ -->
  <div class="q">
    <p class="qnum">Question 5</p>
    <h2>Three problems it could not handle, and what is missing</h2>

    <div class="cap cant">
      <div>
        <h4>1. A customer requests a refund</h4>
        <p>If a customer requested a refund, Accounting would need a new MCP tool to process refunds
        and update the payment records. Customer Service can handle the communication.</p>
        <div class="need"><b>What is missing</b>
        There is no refund tool among the 19, and <code>record_payment</code> only ever debits the
        account &mdash; it subtracts from the balance and marks an invoice paid. The
        <code>payments</code> table has no refund <code>kind</code> and no link to a customer. There
        is also nothing to refund <em>against</em>: no table records what a named customer bought or
        what they paid. So Accounting would need <code>process_refund</code>, a
        <code>customer_orders</code> table to tie it to, and an approval kind of its own &mdash;
        money leaving the shop in the other direction still needs a human.</div>
      </div>

      <div>
        <h4>2. Forecasting future demand</h4>
        <p>If the shop wanted to forecast future demand, Inventory should have access to historical
        sales data and a forecasting tool, to better estimate how much stock to order. This would
        help reduce inventory shortages significantly and avoid running out of stock.</p>
        <div class="need"><b>What is missing</b>
        The shop has no memory. None of the 12 tables holds a sale, a date of sale, or any history
        at all &mdash; <code>inventory</code> is a single snapshot of what is on the shelf right now,
        and <code>desk</code> holds one date. Inventory would need a <code>sales</code> table with
        dated line items, then <code>get_sales_history(sku, weeks)</code> and
        <code>forecast_demand(sku, size, weeks)</code>. This is the largest gap of the three: it is
        not one missing tool, it is a missing dimension &mdash; time.</div>
      </div>

      <div>
        <h4>3. A vendor shipment is delayed</h4>
        <p>If a vendor shipment was delayed, Inventory would need a tracking tool to check the status
        of the delivery. Customer Service should be notified as well, so that the customer can be
        told. It helps manage the customer experience and reduces uncertainty.</p>
        <div class="need"><b>What is missing</b>
        <code>purchase_orders</code> records <code>expected_days</code> at the moment an order is
        placed and then never changes &mdash; there is no received date, no carrier, no actual
        delivery status, and no tool that updates any of it. Inventory would need
        <code>check_shipment_status(purchase_order_id)</code> and
        <code>record_delivery(purchase_order_id, received_qty)</code>, which would also finally let
        stock increase when goods arrive. The notification side is the harder half: nothing today
        pushes anything to another agent. Customer Service only ever acts because the orchestrator
        called it, so the shop would need an event or a queue &mdash; something that says a delivery
        slipped and a customer is waiting on it.</div>
      </div>
    </div>

    <h3>The pattern behind all three</h3>
    <p>They are the same shape. The agents are good at reading the present state of the shop and poor
    at anything else, because almost every tool is a reader. Of the 19 MCP tools only six write, and
    four of those sit behind human approval. That was a deliberate safety choice and I stand by it
    &mdash; but it means the system can describe a problem far better than it can fix one, which is
    roughly what tickets 101 and 103 demonstrated.</p>

    <p>The other thing all three need is agents actually talking to each other: refunds need
    Accounting and Customer Service, delays need Inventory and Customer Service. Right now that
    only happens when one agent explicitly calls another, and across three tickets that happened
    exactly once.</p>
  </div>

'''

SUMMARY_ADDITION = '''    <p>The last thing I took away is that adding more agents does not necessarily solve a problem
    if they do not communicate with each other. Five agents with clear job descriptions still left
    the invoice unaddressed on two tickets, because no one passed it to the agent whose job it was.
    The structure was there; the handoff was not.</p>
'''


def main() -> None:
    s = HTML.read_text(encoding="utf-8")
    if "If a customer requested a refund, Accounting would need" in s:
        print("already applied")
        return

    i = s.index(Q5_START)
    j = s.index(CLOSER_MARK)
    s = s[:i] + NEW_Q5 + s[j:]

    # Close the summary with the lesson, just before its final paragraph.
    anchor = "    <p>The encouraging part is where the line fell."
    if anchor not in s:
        raise SystemExit("summary anchor not found")
    s = s.replace(anchor, SUMMARY_ADDITION + anchor, 1)

    HTML.write_text(s, encoding="utf-8")
    print("Q5 replaced with the owner's answer")
    print("summary closed with their lesson on communication")


if __name__ == "__main__":
    main()
