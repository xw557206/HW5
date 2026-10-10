"""Replace Question 4 with the owner's own answer.

Their wording, grammar tidied only. Each category is tied to a concrete new
scenario the shop could actually meet, using real rows from the database.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

Q4_START = "  <!-- ============ Q4 ============ -->"
Q5_START = "  <!-- ============ Q5 ============ -->"

NEW_Q4 = '''  <!-- ============ Q4 ============ -->
  <div class="q">
    <p class="qnum">Question 4</p>
    <h2>Three problems the team could already handle</h2>

    <p>The agent team could handle several problems the shop runs into, and the three runs we did
    already show how each one would be tested.</p>

    <div class="cap can">
      <div>
        <h4>1. Out-of-stock orders</h4>
        <p>Inventory could use the check to confirm the stock level and any restock options, and
        Customer Service can handle the rest of the communication with the customer.</p>
        <p><strong>A concrete case:</strong> someone asks for the Crest Mug. <code>CC-MUG-CREST</code>
        sits at qty 0 in Aisle D, but its supplier is <strong>Elm City Gifts</strong>, who have
        <strong>no unpaid invoices</strong> and a 3-day lead.</p>
        <div class="ev" style="margin:9px 0 0"><b>Why this is a better test than ticket 101.</b>
        Here the vendor is actually orderable, so the run would reach
        <code>request_approval</code> for a purchase order and then
        <code>create_purchase_order</code> &mdash; two write tools that no run has exercised yet,
        because invoice #501 blocked the only apparel vendor every time.</div>
      </div>

      <div>
        <h4>2. Overdue vendor invoices</h4>
        <p>Accounting should check the invoice and the cash before sending the request for approval
        for payment.</p>
        <p><strong>A concrete case:</strong> invoice #501 itself &mdash; $840 to Bulldog Print Co,
        due 2026-08-28, three days overdue. Every tool needed already exists:
        <code>list_outstanding_invoices</code> and <code>get_cash_position</code> to establish it,
        <code>request_approval</code> to put it in front of a person.</p>
        <div class="ev" style="margin:9px 0 0"><b>The awkward part.</b> This is exactly the problem
        the team already had in front of it on two tickets and never raised. The capability is
        there; the follow-through was not. At $3,400 the shop could have afforded both this and the
        rent ($3,240 together, leaving $160).</div>
      </div>

      <div>
        <h4>3. Discount requests</h4>
        <p>Accounting should review the pricing and margins, and make sure of the inventory level.</p>
        <p><strong>A concrete case:</strong> the lacrosse team wants 15 caps at a discount.
        <code>CC-HAT-BLUE</code> has <strong>40 in stock</strong> at cost $6, list $22, so
        <code>quote_bulk_discount</code> returns a $6 floor and a 72.7% maximum discount.</p>
        <div class="ev" style="margin:9px 0 0"><b>Why it is cleaner than ticket 103.</b> There is no
        shortfall and no blocked vendor, so the discount is the only question &mdash; which is what
        that tool was built to answer. Ticket 103 stalled because supply and price were tangled
        together.</div>
      </div>
    </div>

    <h3>But I would want additional checks</h3>
    <p>These are demonstrated in the existing runs, so I am fairly confident the team could take them
    on. I would still want additional checks first, given the inventory error that showed up.</p>

    <div class="ev"><b>Why that matters for all three.</b> Every one of these categories depends on a
    quantity being correct. Out-of-stock orders need the shortfall right before anything is ordered;
    discount requests need the available quantity right before a price is agreed; and a purchase
    order built on a wrong number spends real money on the wrong amount of stock. On ticket 103
    Inventory reported a shortfall of 4 when the true figure was 12, and the Boss review did not
    catch it. Nothing went wrong that time because the vendor was blocked anyway &mdash; the error
    never reached a decision. In the Crest Mug case the vendor is <em>not</em> blocked, so the same
    mistake would turn straight into a wrong order.</p>

    <p>So before trusting these, I would want the shortfall arithmetic computed by the tool and
    returned as a field rather than worked out by the agent in prose, and I would want any quantity
    that drives a purchase order checked against the catalogue a second time at the point the order
    is placed.</p>
  </div>

'''


def main() -> None:
    s = HTML.read_text(encoding="utf-8")
    if "The agent team could handle several problems the shop runs into" in s:
        print("already applied")
        return
    i = s.index(Q4_START)
    j = s.index(Q5_START)
    s = s[:i] + NEW_Q4 + s[j:]
    HTML.write_text(s, encoding="utf-8")
    print("Q4 replaced with the owner's answer")


if __name__ == "__main__":
    main()
