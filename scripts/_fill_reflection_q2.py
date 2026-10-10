"""Open Question 2 with the owner's own expectation about delegation.

Their wording, grammar tidied only. The analysis that follows is unchanged.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "output" / "desk_tickets.html"

ANCHOR = """    <p class="qnum">Question 2</p>
    <h2>Actual workflows against what I expected</h2>
"""

OWNER_INTRO = """    <p class="qnum">Question 2</p>
    <h2>Actual workflows against what I expected</h2>

    <p>I understand how each ticket should be handled, and I expect the leader to delegate based on
    each agent&rsquo;s specific capacity &mdash; inventory handling to Inventory, the lease and rent
    to Facilities, quality reviews to whoever is actually positioned to check the work, pricing and
    cash to Accounting. That is the whole reason for having five agents instead of one.</p>

    <p>What I got was closer to a filing system than a manager. The ticket went to whoever owns that
    ticket <em>type</em>, and then that agent mostly worked alone. The Boss did not look at a ticket
    and decide who was best placed to handle each part of it; it reviewed afterwards. On 101 that
    meant the stock question went to Customer Service rather than Inventory, and the invoice
    question went to nobody at all.</p>
"""


def main() -> None:
    s = HTML.read_text(encoding="utf-8")
    if OWNER_INTRO.strip()[:80] in s and "I understand how each ticket should be handled" in s:
        print("already applied")
        return
    if s.count(ANCHOR) != 1:
        raise SystemExit(f"anchor found {s.count(ANCHOR)} times, expected 1")
    s = s.replace(ANCHOR, OWNER_INTRO, 1)
    HTML.write_text(s, encoding="utf-8")
    print("Q2 now opens with the owner's delegation expectation")


if __name__ == "__main__":
    main()
