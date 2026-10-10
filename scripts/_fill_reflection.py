"""Replace the Reflection placeholder in desk_tickets.html.

Written against the real records: output/audit_trail.json,
output/resolved_tickets.json, the Cash tab and the working database.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

START = '<section class="panel" id="p-reflect"'
END = "</section>\n\n</main>"

BODY = '''<section class="panel" id="p-reflect" role="tabpanel" aria-labelledby="tab-reflect" hidden>
  <p class="eyebrow">Reflection &middot; what actually happened</p>

  <div class="callout info" style="margin-top:0;margin-bottom:24px">
    <b>Where things stand as I write this.</b> All three tickets ran against the live model and the
    real database. None of them is resolved: 101 is <code>blocked</code>, 102 is
    <code>waiting_approval</code>, and 103 is still <code>open</code> in the database even though the
    run concluded it was blocked. One approval ($2,400 rent) is pending my decision, one customer draft
    exists, no payment has been made, and the balance is unchanged at $3,400. Everything below is based
    on those records, not on how I hoped it would go.
  </div>

  <!-- ============ Q1 ============ -->
  <div class="q">
    <p class="qnum">Question 1</p>
    <h2>How well did the agents handle each ticket?</h2>

    <h3>Ticket 102 &mdash; rent. The one that went right.</h3>
    <p>Facilities did this almost perfectly. Five tool calls, no wasted motion: read the ticket, checked
    the rent, checked the cash, raised the approval, updated the status. It got the date arithmetic right
    against the shop&rsquo;s stored date rather than the real one, it noticed rent had not already been
    paid, and it stated what the balance would be afterwards.</p>
    <div class="ev"><b>Evidence.</b> <code>check_rent_due</code> returned $2,400 due 2026-09-02, 2 days
    from the shop date. <code>request_approval</code> created approval&nbsp;#1 and returned
    <code>requires_human_approval: true</code>. The agent then stopped. The balance is still $3,400.</div>
    <p>That last part is the bit I care about most. The agent had <code>record_payment</code> in its
    toolset the whole time and did not reach for it.</p>

    <h3>Ticket 101 &mdash; the tee. Right answer, shaky reasoning.</h3>
    <p>Customer Service got to the correct conclusion and wrote a decent draft. But it never called
    <code>check_vendor_status</code> &mdash; it learned the vendor was blocked from the
    <code>restock_options</code> field inside <code>check_order_fulfillment</code>. That worked, though
    only because I had built that composite tool. A thinner tool and the agent would have missed it.</p>
    <p>The Boss&rsquo;s review is where it gets uncomfortable.</p>
    <div class="ev"><b>Evidence.</b> The Boss called
    <code>check_order_fulfillment({"sku": "bulldog_tee_white"})</code>. That SKU does not exist &mdash;
    the real one is <code>CC-TEE-WHITE</code>. The tool returned <code>product_name: null</code> and
    <code>qty_on_hand: 0</code>, and the Boss took the zero as confirmation that size S was out of
    stock.</div>
    <p>It got the right answer from a query about a product that is not in the catalogue. That is luck,
    not verification, and it is as much my fault as the model&rsquo;s: my tool returns a zero quantity
    for an unknown SKU, which is indistinguishable from a real out-of-stock unless you read the prose
    summary. A tool that refused an unknown SKU outright would have caught it.</p>

    <h3>Ticket 103 &mdash; the discount. Most collaboration, most mistakes.</h3>
    <p>This one produced the only real agent-to-agent delegation in the whole exercise, and also the two
    worst errors.</p>
    <div class="ev"><b>Evidence.</b> Accounting asked Inventory about restocking 12 units. Inventory
    replied: &ldquo;the shelf has 8, leaving a shortfall of 4&rdquo;. That is wrong &mdash; it subtracted
    the 8 already on the shelf from the 12 needed <em>on top of</em> those 8. The true shortfall is 12
    of 20. The Boss reviewed the run and did not catch it.</div>
    <div class="ev"><b>Evidence.</b> The Boss&rsquo;s own summary contains the sentence &ldquo;exceeds
    the current $1,000.00 available-to-commit amount only by? It does not exceed it&rdquo;. The numbers
    behind it were right; the writing was not.</div>
    <p>Accounting was right not to raise a price override, though &mdash; the club never named a price,
    so there was nothing concrete to approve. Inventing one would have been worse.</p>
    <p>The real failure is that nobody wrote the status back. The run concluded &ldquo;blocked&rdquo; and
    the ticket is still <code>open</code>. Facilities and Customer Service both called
    <code>update_ticket_status</code>; Accounting did not. Nothing in the system forces it.</p>

    <h3>Did the right agents get involved?</h3>
    <p>Mostly, but almost by accident. Routing is a lookup on the ticket <code>type</code> column, so
    each ticket went to whoever owns that type. For 102 and 103 that was fine. For 101 it sent a
    stock problem to Customer Service, which then had to answer a stock question itself.</p>
    <p>The bigger gap is who <em>didn&rsquo;t</em> show up. Invoice #501 blocks both 101 and 103, and
    Accounting is the agent who could have raised a payment request to clear it. On 101 Accounting was
    never called. On 103 Accounting was the lead and still did not raise it &mdash; it treated the
    blocked vendor as a fact to report rather than a problem to solve.</p>
  </div>

  <!-- ============ Q2 ============ -->
  <div class="q">
    <p class="qnum">Question 2</p>
    <h2>Actual workflows against what I expected</h2>

    <table class="ledger" style="margin-bottom:18px">
      <thead><tr><th>Ticket</th><th>I expected</th><th>What happened</th><th>Verdict</th></tr></thead>
      <tbody>
        <tr><td><strong>101</strong></td><td>Inventory &rarr; Accounting &rarr; Customer Service</td><td>Customer Service &rarr; Boss</td><td>Two of three agents never appeared</td></tr>
        <tr><td><strong>102</strong></td><td>Facilities &rarr; Accounting</td><td>Facilities alone &rarr; Boss</td><td>Right lead, Accounting skipped</td></tr>
        <tr><td><strong>103</strong></td><td>Inventory &rarr; Accounting &rarr; Customer Service</td><td>Accounting &rarr; Inventory &rarr; Boss</td><td>Right agents, different order, no customer reply</td></tr>
      </tbody>
    </table>

    <h3>Unexpected delegations</h3>
    <p>Only one delegation happened in three runs: Accounting calling <code>ask_inventory</code> on 103.
    I expected delegation to be the normal way these agents worked. In practice they overwhelmingly
    preferred their own tools, which I now think is the right instinct &mdash; a tool call is cheap and a
    delegation costs a whole model run.</p>
    <p>One record is misleading and I want to flag it rather than quietly fix it: the Boss&rsquo;s audit
    entry for ticket 102 lists <code>delegated_to: ["facilities"]</code>, but the Boss never called an
    <code>ask_*</code> tool. The orchestrator routed to Facilities; the model reported that routing as
    its own delegation. The step list in <code>audit_trail.json</code> is accurate &mdash; the
    self-reported field is not.</p>

    <h3>Unnecessary steps</h3>
    <p>The Boss reviewing every ticket is the most expensive habit in the system.</p>
    <div class="ev"><b>Evidence.</b> Across the three tickets, specialists made 12 tool calls doing the
    work and the Boss made 15 reviewing it. On 102 the Boss re-read the rent, the cash and the approval
    that Facilities had just created &mdash; and reported that everything matched. On 101 its review
    introduced the only factual error in the run.</div>
    <p>So the review stage cost more tool calls than the work itself, caught nothing, and added a
    mistake. On this evidence I would make the Boss review conditional &mdash; on money moving, on a
    rule being refused, on a specialist reporting low confidence &mdash; rather than running it every
    time.</p>

    <h3>What matched</h3>
    <p>The business rules behaved exactly as planned, which is the part I was most worried about. No
    agent paid anything. No agent tried to approve its own request &mdash; they could not, because
    <code>decide_approval</code> is filtered out of their toolset. Both communications stayed drafts.
    Every date was judged against 2026-08-31 rather than the real date. And the cash position correctly
    reported $2,400 committed against a $3,400 balance the moment the approval existed, so the money was
    treated as spoken for before it moved.</p>
  </div>

  <!-- ============ Q3 ============ -->
  <div class="q">
    <p class="qnum">Question 3</p>
    <h2>Could one agent plus MCP tools have done this better?</h2>

    <p>For these three tickets: mostly yes, and the records make that fairly clear.</p>

    <p><strong>Ticket 102 is the strongest case.</strong> Facilities resolved it alone in five tool calls.
    The Boss then spent four more confirming it. A single agent with <code>check_rent_due</code>,
    <code>get_cash_position</code> and <code>request_approval</code> would have produced an identical
    outcome for roughly half the model calls.</p>

    <p><strong>Ticket 101 is similar.</strong> Customer Service answered it in four calls. The Boss&rsquo;s
    six-call review added one hallucinated SKU and no new information.</p>

    <p><strong>Ticket 103 is the interesting one</strong>, and it cuts the other way &mdash; partly.
    Accounting genuinely needed vendor information it did not have, and asking Inventory was a reasonable
    move. But Accounting has <code>check_vendor_status</code> in its own toolset. It could have made that
    one call instead of spawning an entire agent run, and it would have avoided importing Inventory&rsquo;s
    arithmetic error.</p>

    <p>What I take from this: the value here is in the <em>tools</em>, not the org chart. The composite
    tools do the heavy lifting &mdash; <code>get_ticket</code> resolves foreign keys in one call,
    <code>check_order_fulfillment</code> bundles stock, alternatives and vendor standing,
    <code>quote_bulk_discount</code> returns the whole margin picture. Once a tool answers the real
    question, the agent calling it barely needs to reason.</p>

    <p>Multiple agents earn their keep in two places, neither of which this dataset exercises much.
    One is <strong>separation of duties</strong>: whoever asks for money should not be whoever judges
    whether the shop can afford it. Facilities doing both on 102 is efficient but it removed that check.
    The other is <strong>specialised prompts</strong> &mdash; Accounting knowing the cost floor is not
    negotiable is prompt knowledge, not tool knowledge, and that would be diluted in one general agent
    carrying every rule at once.</p>

    <p>If I rebuilt this I would keep the five agents but make the Boss a router and an exception
    handler rather than a reviewer, and I would stop treating delegation as the default.</p>
  </div>

  <!-- ============ Q4 ============ -->
  <div class="q">
    <p class="qnum">Question 4</p>
    <h2>Three problems the team could already handle</h2>

    <div class="cap can">
      <div>
        <h4>1. &ldquo;Is the Crest Mug back in stock?&rdquo;</h4>
        <p>A customer asks about <code>CC-MUG-CREST</code>, which sits at qty 0 in Aisle D.</p>
        <p>Customer Service calls <code>check_order_fulfillment</code>, sees zero, and gets
        <code>restock_options</code> back pointing at Elm City Gifts &mdash; who, unlike Bulldog Print Co,
        have <strong>no unpaid invoices</strong> and a 3-day lead. Inventory raises a
        <code>purchase_order</code> approval; Customer Service drafts an honest reply with the real lead
        time.</p>
        <p>This works today, and it is a better test than ticket 101 because the vendor is actually
        orderable &mdash; it would exercise <code>create_purchase_order</code>, which no run has reached.</p>
      </div>
      <div>
        <h4>2. &ldquo;Can the lacrosse team have 15 caps at a discount?&rdquo;</h4>
        <p>A bulk request for <code>CC-HAT-BLUE</code>, which has 40 in stock at cost $6, list $22.</p>
        <p>Accounting calls <code>quote_bulk_discount</code>, gets the $6 floor and a 72.7% maximum
        discount, and raises a <code>price_override</code> approval with a specific price. Unlike ticket
        103 there is no shortfall and no blocked vendor, so the discount is the only question &mdash;
        which is exactly what that tool was built for.</p>
      </div>
      <div>
        <h4>3. &ldquo;Which bills are overdue and can we pay them?&rdquo;</h4>
        <p>A routine end-of-month check with no ticket attached.</p>
        <p>Accounting calls <code>list_outstanding_invoices</code> (invoice #501, 3 days overdue) and
        <code>get_cash_position</code> ($3,400 balance, $2,400 committed to the pending rent). It can
        correctly report that $840 and $2,400 total $3,240 against $3,400, recommend an order, and raise
        the approvals. Every tool for this already exists &mdash; it simply was not asked.</p>
      </div>
    </div>
  </div>

  <!-- ============ Q5 ============ -->
  <div class="q">
    <p class="qnum">Question 5</p>
    <h2>Three problems it could not handle, and what is missing</h2>

    <div class="cap cant">
      <div>
        <h4>1. &ldquo;Where is my order? I was promised it Friday.&rdquo;</h4>
        <p>The shop has no concept of a customer order existing after the conversation. There is a
        <code>tickets</code> table and a <code>purchase_orders</code> table, but nothing recording what a
        named customer bought, for how much, or when it was promised. The agents cannot answer because
        the fact does not exist anywhere.</p>
        <div class="need"><b>What is missing</b>
        A <code>customer_orders</code> table (customer, sku, size, qty, price paid, promised date,
        fulfilment status), plus <code>create_customer_order</code>,
        <code>get_order_status</code> and <code>list_orders_for_customer</code>. Inventory would also
        need to decrement stock on fulfilment, which nothing currently does &mdash; stock is read-only
        across all 19 tools.</div>
      </div>
      <div>
        <h4>2. &ldquo;Three hoodies came through with the crest misprinted.&rdquo;</h4>
        <p>A return or a supplier quality claim. The agents can see stock levels but cannot adjust them,
        cannot record a reason for an adjustment, and cannot raise a credit against a vendor. Right now
        the only way stock changes is if someone edits the database by hand.</p>
        <div class="need"><b>What is missing</b>
        <code>adjust_inventory(sku, size, delta, reason, approval_id)</code> &mdash; gated behind an
        approval, because writeable stock is exactly the capability you do not want an agent holding
        unsupervised. Plus <code>raise_vendor_credit</code> and a <code>stock_adjustments</code> audit
        table. A <strong>Returns</strong> agent would be worth adding: the judgement about whether a
        claim is reasonable is not inventory work and not accounting work.</div>
      </div>
      <div>
        <h4>3. &ldquo;Rent goes up 6% in January &mdash; can we afford next quarter?&rdquo;</h4>
        <p>This is a forecast, and the system has no concept of the future. <code>get_cash_position</code>
        reports one balance on one day. There is no revenue history, no recurring-cost schedule, and
        <code>leases</code> holds only the next due date &mdash; not a term, an escalation clause, or a
        renewal option.</p>
        <div class="need"><b>What is missing</b>
        <code>project_cash_flow(weeks)</code> over scheduled obligations, a <code>revenue</code> or
        <code>sales</code> table to project income from, and lease terms extended with escalation and
        renewal dates. Facilities would also need <code>get_lease_terms</code>. This is the biggest gap
        of the three: it is not one tool, it is a whole dimension &mdash; time &mdash; that the data
        model does not have.</div>
      </div>
    </div>

    <h3>The pattern</h3>
    <p>All three failures are the same shape. The agents are good at reading the present state of the
    shop and poor at anything else, because almost every tool is a reader. Of the 19 MCP tools, only six
    write, and four of those are gated behind human approval. That was a deliberate safety choice and I
    stand by it &mdash; but it means the system can describe a problem far better than it can fix one,
    which is roughly what ticket 101 and ticket 103 demonstrated.</p>
  </div>

  <div class="callout key" style="margin-top:8px"><b>One thing I would change first.</b> Not the agents,
  the tools. If <code>check_order_fulfillment</code> had refused the Boss&rsquo;s invented SKU instead of
  returning a zero, and if <code>update_ticket_status</code> were required before a run could finish,
  two of the three defects on this page would not exist. The guardrails that were written in code held
  perfectly all day. The ones left to the prompt are the ones that slipped.</div>
</section>

</main>'''


def main() -> None:
    s = HTML.read_text(encoding="utf-8")
    i = s.index(START)
    j = s.index(END) + len(END)
    s = s[:i] + BODY + s[j:]
    HTML.write_text(s, encoding="utf-8")
    print("reflection tab filled")
    print("  placeholders remaining:", s.count("Placeholder for now"))


if __name__ == "__main__":
    main()
