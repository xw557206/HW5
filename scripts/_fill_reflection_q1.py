"""Replace Q1 and the closing verdict with the owner's own assessment.

The wording is the owner's, lightly corrected for grammar only. The evidence
boxes underneath each point are drawn from output/audit_trail.json so the
claims can be checked.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

Q1_START = "  <!-- ============ Q1 ============ -->"
Q2_START = "  <!-- ============ Q2 ============ -->"

NEW_Q1 = '''  <!-- ============ Q1 ============ -->
  <div class="q">
    <p class="qnum">Question 1</p>
    <h2>How well did the agents handle each ticket?</h2>

    <p>I would say the agents did a nice job following the rules of this shop. That part I am
    genuinely happy with. Where they struggled was everything after the rules &mdash; actually
    finishing the job.</p>

    <h3>Ticket 102 &mdash; the best example</h3>
    <p>Ticket 102 was the best example of how I wanted it to run. Facilities checked the rent
    payment, confirmed there was cash on the books, and then put in the request for approval.
    No transaction or payment was made in the process.</p>
    <div class="ev"><b>What the record shows.</b> Five tool calls, in order:
    <code>get_ticket</code>, <code>check_rent_due</code>, <code>get_cash_position</code>,
    <code>request_approval</code>, <code>update_ticket_status</code>. Approval&nbsp;#1 was created
    with <code>requires_human_approval: true</code> and the agent stopped there. The balance is
    still $3,400.00 and the <code>payments</code> table is empty.</div>

    <h3>Ticket 101 &mdash; did not do as well</h3>
    <p>Ticket 101 was not doing great compared to ticket 102. The service correctly identified that
    the Bulldog tee was not in stock, and a response was drafted. But the agents failed to take the
    next step and address the unpaid vendor invoice, which caused the restocking to fail.</p>
    <div class="ev"><b>What the record shows.</b> Customer Service confirmed size S at qty 0 and
    wrote draft&nbsp;#1. No agent called <code>request_approval</code> on this ticket, so the $840
    invoice #501 &mdash; the only thing standing between the shop and a restock &mdash; was never
    put in front of a human. The shop could have afforded it: $3,400 on hand against $840.</div>

    <p>I could also see that the leadership used the incorrect SKU when quality-controlling
    inventory, but still accepted the wrong result. That made me question the accuracy and
    reliability of the review process.</p>
    <div class="ev"><b>What the record shows.</b> The Boss called
    <code>check_order_fulfillment({"sku": "bulldog_tee_white"})</code>. The real SKU is
    <code>CC-TEE-WHITE</code>. The tool returned <code>product_name: null</code> and
    <code>qty_on_hand: 0</code> &mdash; which reads exactly like a genuine out-of-stock &mdash; and
    the Boss treated it as confirmation of Customer Service&rsquo;s finding. The conclusion happened
    to be right, but the check that was supposed to verify it did not actually verify anything.</div>

    <h3>Ticket 103 &mdash; the worst performer</h3>
    <p>Ticket 103 was the worst performer. Even though the accounting department communicated the
    inventory problem, inventory got the shortage calculation wrong, and the ticket was not
    updated.</p>
    <div class="ev"><b>What the record shows.</b> Accounting called <code>ask_inventory</code> about
    restocking 12 units. Inventory replied &ldquo;the shelf has 8, leaving a shortfall of 4&rdquo;
    &mdash; it subtracted the 8 already on the shelf from the 12 still needed. The real shortfall is
    12 of 20. The Boss reviewed the run and did not catch it. No agent called
    <code>update_ticket_status</code>, so the ticket is still <code>open</code> in the database even
    though the run concluded it was blocked.</div>

    <h3>Did the right agents get involved?</h3>
    <p>Broadly yes &mdash; each ticket reached an agent whose job it was. The gap was who
    <em>didn&rsquo;t</em> get involved. Invoice #501 blocks both 101 and 103, and Accounting is the
    agent who could have raised a payment request to clear it. On 101 Accounting was never brought
    in at all. On 103 Accounting was actually leading the ticket and still did not raise it &mdash;
    it reported the blocked vendor as a fact rather than treating it as the thing to fix.</p>
  </div>

'''

OLD_CLOSER_MARK = '<div class="callout key" style="margin-top:8px"><b>One thing I would change first.</b>'

NEW_CLOSER = '''<div class="q" style="border-left:4px solid var(--gold)">
    <p class="qnum">In summary</p>
    <h2>My overall verdict</h2>
    <p>Across all three tickets, the agents seemed to understand their roles and responsibilities,
    but they weren&rsquo;t always good at connecting the pieces or following through. They could each
    describe their part of the problem accurately. What they could not do reliably was carry a
    finding to the action it implied &mdash; spotting the blocking invoice but never asking anyone to
    pay it, reaching a conclusion but never writing it back to the ticket.</p>
    <p>The system is overall a good starting point, but <strong>I wouldn&rsquo;t feel comfortable
    letting it run the shop on its own, without quality checks.</strong></p>
    <p>The encouraging part is where the line fell. Every rule I enforced in code held all day: no
    payment without approval, no agent able to approve its own request, communications saved as
    drafts only, and every date judged against the shop&rsquo;s stored date rather than the real one.
    Every rule I left to the prompt slipped at least once. If I carried on with this, I would move
    more of the &ldquo;follow through&rdquo; into code &mdash; make a run refuse to finish without a
    status update, and make the tools reject an unknown SKU instead of quietly returning zero.</p>
  </div>

  <div class="callout key" style="margin-top:8px"><b>One thing I would change first.</b>'''


def main() -> None:
    s = HTML.read_text(encoding="utf-8")

    i = s.index(Q1_START)
    j = s.index(Q2_START)
    s = s[:i] + NEW_Q1 + s[j:]

    k = s.index(OLD_CLOSER_MARK)
    s = s[:k] + NEW_CLOSER + s[k + len(OLD_CLOSER_MARK):]

    HTML.write_text(s, encoding="utf-8")
    print("Q1 replaced with the owner's assessment")
    print("closing verdict added")
    print("  sections now:", s.count('class="qnum"'))


if __name__ == "__main__":
    main()
