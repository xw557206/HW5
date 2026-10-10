"""Fill the three Actual panels in output/desk_tickets.html from the real runs.

Run once. Every figure here comes from output/audit_trail.json and
output/resolved_tickets.json — see scripts/build_outcomes.py.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

WAIT_EXPANDED = """      <div class="pane-hd"><h3>Actual</h3><span class="stamp wait">Not yet run</span></div>
      <div class="pane-body">
        <div class="sec"><h4>Actual agent sequence</h4>
          <div class="waiting"><span class="pulse"></span>Waiting for agent execution</div>
          <div class="skel w70"></div><div class="skel w45"></div></div>
        <div class="sec"><h4>MCP tools called</h4>
          <div class="waiting"><span class="pulse"></span>Waiting for agent execution</div>
          <div class="skel w85"></div><div class="skel w70"></div></div>
        <div class="sec"><h4>Actions taken</h4>
          <div class="waiting"><span class="pulse"></span>Waiting for agent execution</div>
          <div class="skel"></div><div class="skel w70"></div></div>
        <div class="sec"><h4>Final outcome</h4>
          <div class="waiting"><span class="pulse"></span>Waiting for agent execution</div>
          <div class="skel w85"></div></div>
        <div class="sec"><h4>Differences from expectation</h4>
          <div class="waiting"><span class="pulse"></span>Waiting for agent execution</div>
          <div class="skel w70"></div><div class="skel w45"></div></div>
      </div>"""

WAIT_COMPACT = """      <div class="pane-hd"><h3>Actual</h3><span class="stamp wait">Not yet run</span></div>
      <div class="pane-body">
        <div class="sec"><h4>Actual agent sequence</h4><div class="waiting"><span class="pulse"></span>Waiting for agent execution</div><div class="skel w70"></div><div class="skel w45"></div></div>
        <div class="sec"><h4>MCP tools called</h4><div class="waiting"><span class="pulse"></span>Waiting for agent execution</div><div class="skel w85"></div><div class="skel w70"></div></div>
        <div class="sec"><h4>Actions taken</h4><div class="waiting"><span class="pulse"></span>Waiting for agent execution</div><div class="skel"></div><div class="skel w70"></div></div>
        <div class="sec"><h4>Final outcome</h4><div class="waiting"><span class="pulse"></span>Waiting for agent execution</div><div class="skel w85"></div></div>
        <div class="sec"><h4>Differences from expectation</h4><div class="waiting"><span class="pulse"></span>Waiting for agent execution</div><div class="skel w70"></div><div class="skel w45"></div></div>
      </div>"""

T101 = """      <div class="pane-hd"><h3>Actual</h3><span class="stamp part">Ran &middot; blocked</span></div>
      <div class="pane-body">
        <div class="sec"><h4>Actual agent sequence</h4>
          <ol class="seq">
            <li style="--ac:var(--c-cs)"><span class="ag">CS</span><b>Customer Service</b> took the ticket straight from the router &mdash; the Boss did not see it first. 4 tool calls.</li>
            <li style="--ac:var(--c-boss)"><span class="ag">BO</span><b>Boss</b> reviewed afterwards with 6 tool calls of its own.</li>
          </ol>
          <p class="muted" style="margin-top:4px">No agent called <code>ask_*</code>. Inventory and Accounting were never consulted.</p>
        </div>
        <div class="sec"><h4>MCP tools called</h4>
          <p style="font-size:12.5px;color:var(--dim);margin-bottom:5px">Customer Service</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">check_order_fulfillment</span><span class="mini">draft_customer_email</span><span class="mini">update_ticket_status</span></div>
          <p style="font-size:12.5px;color:var(--dim);margin:11px 0 5px">Boss (review)</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">check_order_fulfillment</span><span class="mini">get_cash_position</span><span class="mini">list_outstanding_invoices</span><span class="mini">list_drafts</span><span class="mini">check_vendor_status</span></div>
        </div>
        <div class="sec"><h4>Actions taken</h4>
          <ul>
            <li>Confirmed <strong>size S at qty 0</strong>, with M 5 / L 3 / XL 2 available.</li>
            <li>Identified Bulldog Print Co as blocked by <strong>unpaid invoice #501 ($840, 3 days overdue)</strong>.</li>
            <li>Wrote <strong>draft #1</strong> to Tauhid Zaman &mdash; saved, not sent.</li>
            <li>Moved the ticket to <strong>blocked</strong> with a stamped note.</li>
            <li><strong>No approval raised</strong>, no money committed.</li>
          </ul>
        </div>
        <div class="sec"><h4>Final outcome</h4>
          <p><strong>blocked.</strong> The tee cannot be supplied in size S and cannot be reordered while invoice #501 is unpaid. 8 model calls, 10 tool calls, $0 cash impact.</p>
        </div>
        <div class="sec"><h4>Differences from expectation</h4>
          <div class="diff diff-off"><b>Wrong first contact.</b> I expected Inventory. The router sent it to Customer Service, because <code>DEFAULT_ROUTING</code> maps <code>customer_order</code> that way. Defensible &mdash; CS owns the customer &mdash; but not what I planned.</div>
          <div class="diff diff-off"><b>Accounting never appeared.</b> I expected it to review invoice #501 and raise a payment request. Nobody did, so the one action that would unblock this ticket was never proposed.</div>
          <div class="diff diff-bad"><b>The Boss used a SKU that does not exist.</b> It called <code>check_order_fulfillment("bulldog_tee_white")</code> instead of <code>CC-TEE-WHITE</code>. The tool returned <code>qty_on_hand: 0</code>, which looks identical to a real out-of-stock, and the Boss read it as confirmation. It reached the right conclusion by luck.</div>
          <div class="diff diff-match"><b>Everything else matched.</b> The stock figures, the alternatives offered, the vendor blocker and the draft-only reply all landed as expected.</div>
        </div>
      </div>"""

T102 = """      <div class="pane-hd"><h3>Actual</h3><span class="stamp part">Ran &middot; awaiting approval</span></div>
      <div class="pane-body">
        <div class="sec"><h4>Actual agent sequence</h4>
          <ol class="seq">
            <li style="--ac:var(--c-fac)"><span class="ag">FA</span><b>Facilities</b> handled the whole ticket alone in 5 tool calls &mdash; including the cash check and the approval request.</li>
            <li style="--ac:var(--c-boss)"><span class="ag">BO</span><b>Boss</b> reviewed with 4 tool calls, re-reading the rent, the cash position and the approval record.</li>
          </ol>
        </div>
        <div class="sec"><h4>MCP tools called</h4>
          <p style="font-size:12.5px;color:var(--dim);margin-bottom:5px">Facilities</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">check_rent_due</span><span class="mini">get_cash_position</span><span class="mini">request_approval</span><span class="mini">update_ticket_status</span></div>
          <p style="font-size:12.5px;color:var(--dim);margin:11px 0 5px">Boss (review)</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">check_rent_due</span><span class="mini">get_cash_position</span><span class="mini">get_approval</span></div>
        </div>
        <div class="sec"><h4>Actions taken</h4>
          <ul>
            <li>Verified <strong>$2,400 to Elm City Properties, due 2026-09-02 &mdash; 2 days out</strong>, and that rent was not already paid.</li>
            <li>Checked cash: <strong>$3,400 available</strong>, leaving $1,000 after payment.</li>
            <li>Raised <strong>approval #1</strong> (<code>rent_payment</code>, $2,400) and stopped.</li>
            <li>Moved the ticket to <strong>waiting_approval</strong>.</li>
          </ul>
        </div>
        <div class="sec"><h4>Final outcome</h4>
          <p><strong>waiting_approval.</strong> Exactly as designed &mdash; the agent prepared the payment and a human must decide. 7 model calls, 9 tool calls, $0 moved. Cash now reports $2,400 committed and $1,000 free.</p>
        </div>
        <div class="sec"><h4>Differences from expectation</h4>
          <div class="diff diff-match"><b>First contact was right.</b> Facilities, as planned.</div>
          <div class="diff diff-off"><b>Accounting was not involved.</b> I expected Facilities to establish the obligation and Accounting to check cash and prepare the payment. Facilities did all of it. Arguably better &mdash; it saved a delegation and a model run &mdash; but it means no second pair of eyes on the cash decision.</div>
          <div class="diff diff-match"><b>The approval gate held.</b> <code>request_approval</code> was called, nothing was paid, and the balance is untouched.</div>
        </div>
      </div>"""

T103 = """      <div class="pane-hd"><h3>Actual</h3><span class="stamp part">Ran &middot; blocked</span></div>
      <div class="pane-body">
        <div class="sec"><h4>Actual agent sequence</h4>
          <ol class="seq">
            <li style="--ac:var(--c-acc)"><span class="ag">AC</span><b>Accounting</b> took the ticket and priced the request. 4 tool calls.</li>
            <li style="--ac:var(--c-inv)"><span class="ag">IN</span><b>Inventory</b> was pulled in by Accounting via <code>ask_inventory</code> &mdash; the only genuine agent-to-agent delegation across all three runs. 3 tool calls at depth 1.</li>
            <li style="--ac:var(--c-boss)"><span class="ag">BO</span><b>Boss</b> reviewed with 5 tool calls.</li>
          </ol>
        </div>
        <div class="sec"><h4>MCP tools called</h4>
          <p style="font-size:12.5px;color:var(--dim);margin-bottom:5px">Accounting</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">quote_bulk_discount</span><span class="mini">get_cash_position</span><span class="mini">ask_inventory</span></div>
          <p style="font-size:12.5px;color:var(--dim);margin:11px 0 5px">Inventory (delegated)</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">check_order_fulfillment</span><span class="mini">check_vendor_status</span></div>
          <p style="font-size:12.5px;color:var(--dim);margin:11px 0 5px">Boss (review)</p>
          <div class="toolset"><span class="mini">get_ticket</span><span class="mini">get_cash_position</span><span class="mini">list_outstanding_invoices</span><span class="mini">list_pending_approvals</span><span class="mini">check_vendor_status</span></div>
        </div>
        <div class="sec"><h4>Actions taken</h4>
          <ul>
            <li>Priced the request: <strong>cost $22, list $58</strong>, $1,160 at list, $720 margin, break-even floor $22.</li>
            <li>Confirmed <strong>8 of 20 mediums on hand</strong>.</li>
            <li>Confirmed the reprint vendor is blocked by the same invoice #501.</li>
            <li><strong>No price-override approval raised</strong> &mdash; the club never named a price to approve.</li>
            <li><strong>No ticket status update.</strong> The ticket is still <code>open</code> in the database.</li>
          </ul>
        </div>
        <div class="sec"><h4>Final outcome</h4>
          <p><strong>Blocked in substance, but still <code>open</code> in the database.</strong> 11 model calls, 12 tool calls, $0 cash impact. The run concluded the ticket was blocked; no agent recorded that conclusion on the ticket itself.</p>
        </div>
        <div class="sec"><h4>Differences from expectation</h4>
          <div class="diff diff-off"><b>Accounting went first, not Inventory.</b> The router follows the ticket type (<code>price_override</code>). It worked out: Accounting pulled Inventory in itself.</div>
          <div class="diff diff-match"><b>The delegation I hoped for actually happened.</b> Accounting &rarr; Inventory is the one real <code>ask_*</code> call in the whole exercise, and the question it asked was specific and sensible.</div>
          <div class="diff diff-bad"><b>Inventory got the arithmetic wrong.</b> Asked about restocking 12, it reported &ldquo;the shelf has 8, leaving a shortfall of 4&rdquo; &mdash; subtracting stock that was already counted. The true shortfall is 12 of 20. The Boss did not catch it.</div>
          <div class="diff diff-bad"><b>The Boss&rsquo;s summary was partly incoherent</b> &mdash; it wrote &ldquo;exceeds the current $1,000.00 available-to-commit amount only by? It does not exceed it&rdquo;. The underlying figures were right; the sentence was not.</div>
          <div class="diff diff-off"><b>Customer Service never wrote a reply.</b> I expected a draft to the Yale AI Club. None exists.</div>
        </div>
      </div>"""


def main() -> None:
    s = HTML.read_text(encoding="utf-8")

    if s.count(WAIT_EXPANDED) != 1:
        raise SystemExit(f"ticket 101 placeholder found {s.count(WAIT_EXPANDED)} times, expected 1")
    s = s.replace(WAIT_EXPANDED, T101, 1)

    if s.count(WAIT_COMPACT) != 2:
        raise SystemExit(f"compact placeholders found {s.count(WAIT_COMPACT)}, expected 2")
    s = s.replace(WAIT_COMPACT, T102, 1)   # 102 comes first in the document
    s = s.replace(WAIT_COMPACT, T103, 1)   # then 103

    HTML.write_text(s, encoding="utf-8")
    print("filled all three Actual panels")
    print("remaining 'Waiting for agent execution':", s.count("Waiting for agent execution"))


if __name__ == "__main__":
    main()
