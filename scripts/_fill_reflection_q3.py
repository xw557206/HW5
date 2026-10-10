"""Replace Question 3 with the owner's own answer.

Their wording, grammar tidied only. The evidence boxes underneath are drawn
from output/audit_trail.json so each claim can be checked.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

Q3_START = "  <!-- ============ Q3 ============ -->"
Q4_START = "  <!-- ============ Q4 ============ -->"

NEW_Q3 = '''  <!-- ============ Q3 ============ -->
  <div class="q">
    <p class="qnum">Question 3</p>
    <h2>Could one agent plus MCP tools have done this better?</h2>

    <p>Looking back, I don&rsquo;t think every task necessarily benefited from having multiple
    agents. While dividing responsibilities makes sense for more complicated problems, it can also
    create unnecessary communication and additional AI calls.</p>

    <p>For example, in Ticket 102, Facilities handled the entire rent review on its own &mdash;
    including checking the lease, confirming the available cash, and submitting the payment for
    approval. The Boss then went back and checked the same rent, cash balance, and approval request,
    which felt somewhat repetitive.</p>

    <div class="ev"><b>What the record shows.</b> Facilities made five tool calls and finished the
    ticket. The Boss then made four more: <code>get_ticket</code>, <code>check_rent_due</code>,
    <code>get_cash_position</code>, <code>get_approval</code> &mdash; the same three facts Facilities
    had just established, plus the approval it had just created. Its conclusion was that everything
    matched.</div>

    <p>I think a single Accounting agent with access to the right MCP tools could have handled this
    ticket just as effectively, without involving Facilities and without requiring another round of
    review. Of course, having the Boss double-check financial decisions adds some protection, but in
    this case I&rsquo;m not sure the additional steps provided enough value to justify the extra
    complexity.</p>

    <div class="ev"><b>What the record shows.</b> Across all three tickets the specialists made 12
    tool calls doing the work, and the Boss made 15 reviewing it. On 102 the review confirmed what
    was already correct. On 101 the review introduced the only factual error in the entire run
    &mdash; the invented SKU. So the checking stage cost more than the work, caught nothing, and was
    itself the least reliable part.</div>

    <p>This made me realise that having more agents doesn&rsquo;t necessarily mean the system will
    work better, especially for relatively straightforward tasks.</p>

    <h3>Where the extra agents did earn their place</h3>
    <p>Ticket 103 is the one case that cuts the other way, at least partly. Accounting genuinely
    needed vendor information it did not have, and asking Inventory was a reasonable move &mdash;
    that was the only real agent-to-agent call in the whole exercise. But even there, Accounting
    already had <code>check_vendor_status</code> in its own toolset. One tool call would have done
    it, and it would have avoided importing Inventory&rsquo;s arithmetic error.</p>

    <p>What I take from this is that the value sits in the <em>tools</em> more than the org chart.
    <code>get_ticket</code> resolves a ticket and everything it links to in one call;
    <code>check_order_fulfillment</code> bundles stock, alternatives and vendor standing;
    <code>quote_bulk_discount</code> returns the whole margin picture. Once a tool answers the real
    question, the agent calling it barely has to reason. The agents were only as good as the tool
    they happened to reach for.</p>

    <p>If I rebuilt this, I would keep the five agents for the genuinely messy tickets but make the
    Boss a router and an exception handler rather than a reviewer of everything &mdash; triggered by
    money moving or a rule being refused, not by every ticket that happens to finish.</p>
  </div>

'''


def main() -> None:
    s = HTML.read_text(encoding="utf-8")
    if "Looking back, I don&rsquo;t think every task" in s:
        print("already applied")
        return
    i = s.index(Q3_START)
    j = s.index(Q4_START)
    s = s[:i] + NEW_Q3 + s[j:]
    HTML.write_text(s, encoding="utf-8")
    print("Q3 replaced with the owner's answer")


if __name__ == "__main__":
    main()
