# Dashboard Design

How the Campus Customs operations dashboard is put together, and why.

The aim was an operations command centre that feels like it belongs to a
business school: calm, precise, and quick to read under pressure — not a
toy, and not a wall of raw JSON.

---

## Layout

A two-column grid on desktop, collapsing to one column below 1080px.

| area | holds | why there |
| --- | --- | --- |
| **Masthead** | crest, title, shop date, tool count, **cash plate**, Reset | The two things always worth knowing — what day it is for the shop, and how much money there is — never scroll away. |
| **Left column** | tickets → run bar → last outcome → the team | The work you act on, in the order you act on it: pick, run, read the result. |
| **Right column** | approvals → agent activity | The two things that *change while you watch*. Approvals sit at the top right, the first place the eye lands. |

The left column is slightly wider (`1.05fr` to `1fr`). Ticket cards carry
more text than approval cards, and an even split left them cramped.

The run bar only appears once a ticket is selected. There is no point
offering "Run agent team" before there is something to run.

---

## Colour and type

The same tokens as the Problem 6 planning page, so the two feel like one
application rather than two assignments.

| token | value | used for |
| --- | --- | --- |
| `--yale` | `#00356b` | primary, masthead, buttons |
| `--yale-deep` / `--yale-ink` | `#012048` / `#00172f` | gradient depth, headings |
| `--bg` / `--cream` | `#fbfaf7` / `#f6f2ea` | warm off-white page, run bar |
| `--gold` / `--gold-ink` | `#b08d3f` / `#8a6a22` | hairlines, crest, small-caps labels |

**The background is warm, not cool grey.** It reads as paper, which makes
the blue look richer and stops the page looking like a default admin panel.

**Gold is split in two by contrast ratio, not taste.** `#b08d3f` is only
3.1:1 on white, so it is decoration only — rules, borders, the crest. Label
text uses `#8a6a22` at 5.2:1, which passes WCAG AA. The same split was
measured and applied in the HW 4 storefront.

**Fraunces for display, Inter for UI.** A serif ticket subject beside
sans-serif body copy does the hierarchy work without extra weight or size.
Both fall back to Georgia and the system stack offline.

Gold hairlines close the masthead and head each card — the one repeated
motif tying the page together.

---

## How the agents are represented

Each agent has a fixed colour and two-letter mark, so a run can be followed
by colour alone without reading every line:

| agent | mark | colour | owns |
| --- | --- | --- | --- |
| Boss | **BO** | Yale blue `#00356b` | triage, delegation, review |
| Inventory | **IN** | green `#1d7a6c` | stock, vendors, purchase orders |
| Accounting | **AC** | gold `#8a6a22` | invoices, cash, pricing |
| Facilities | **FA** | violet `#6b4e9e` | the lease, rent, premises |
| Customer Service | **CS** | terracotta `#b3503a` | anything a customer reads |

Initials rather than illustrations. At 22px on a ticket card an icon becomes
a smudge; two letters stay legible, and the colour carries the identity.

Avatars appear in three places, each answering a different question:

- **On a ticket card** — *who touched this?* They accumulate as agents
  participate, so a card shows its own history at a glance.
- **On the timeline** — *who is speaking?* With a pulsing ring while a run
  is live.
- **In the team legend** — *who are these people?* A standing reference so
  the colours mean something before the first run.

### The timeline

The timeline is the audit trail rendered, not a summary of it. Each entry
shows what the agent was asked, what it concluded, the MCP tools it called
as monospace chips, and who it delegated to as a dashed pill with an arrow —
so **Boss → Inventory → Accounting** is visible as a shape, not inferred
from prose.

Refusals get their own red block: *"Rule stopped this."* A guardrail firing
is the most interesting thing that can happen in a run, and burying it in
grey text would waste it.

Entries slide in from the left as they arrive, which makes a live run feel
like work being done rather than a list redrawing.

---

## Ticket status

Four states, each with its own pill, because the difference between them is
the whole point of a human-in-the-loop system:

| pill | colour | means |
| --- | --- | --- |
| **Open** | amber | nothing has run yet |
| **Agents working** | blue, pulsing ring | a run is in flight |
| **Awaiting approval** | Yale mist | the agents finished; a person must decide |
| **Resolved** | green | genuinely done |
| **Blocked** | red | a rule or a missing fact stops it |

**A ticket shows Resolved only when the backend says `resolved`.** If
approvals are pending it shows *Awaiting approval* instead. The frontend
never promotes a status on its own — that would turn an honest system into a
dishonest-looking one.

While a run is live the selected card gets a pulsing border ring and the run
bar shows an elapsed timer. One ring and one timer: enough to show the
system is alive, not so much that it distracts.

---

## Cash

The balance sits in the masthead, in the display serif at 25px — large
enough to read across a desk, small enough not to dominate.

**It flashes gold for 1.3 seconds after an approved payment changes it.**
That is the moment a person most wants confirmation that something real
happened, and a number that silently changes is easy to miss.

When money is committed to open requests, a second line appears showing what
is genuinely free versus what is spoken for. It stays hidden when nothing is
committed, so the common case stays uncluttered.

---

## Approvals

Pending requests come first, each showing the amount in display serif, the
kind, the ticket, the requesting agent, and the reason in plain words — so a
decision can be made from the card alone, without opening the database.

Approve is solid green, Reject is an outlined red ghost button. The
asymmetry is deliberate: approving moves real money, so it should look like
the deliberate act, while rejecting stays visually quiet and safe.

Decided requests move to a separate list below, showing who decided and any
note. They are not deleted — the record of a rejection matters as much as
the record of a payment.

Both buttons call `POST /approvals/{id}`. Nothing is faked client-side, and
a request refused by a business rule after approval shows an amber toast
explaining why, rather than a success message.

---

## Feedback and states

Every state the user can land in has a designed answer:

- **Loading** — shimmer bars shaped like the content that is coming, not a
  spinner, so the layout does not jump when data arrives.
- **Empty** — an icon and a sentence that explains *why* it is empty. The
  approvals empty state says agents raise requests but can never approve
  their own, which teaches the rule at the moment it is relevant.
- **Error** — if the backend is unreachable the page says so plainly, gives
  the exact `uvicorn` command, and offers a Try again button.
- **Success** — toasts, colour-coded and self-dismissing after 7 seconds:
  green for an executed payment, amber for a rule block, red for a failure.
- **Confirmation** — Reset opens a modal naming exactly what will be
  cleared, and that the original database is never touched. Escape or a
  backdrop click cancels.

---

## Why this is pleasant to use

- **Nothing important moves.** The cash and the shop date stay in the
  masthead; approvals stay top-right. Muscle memory works after one run.
- **Colour means one thing.** Each agent owns a hue, and status colours are
  never reused for anything else — so the page can be read at a glance.
- **Motion is informative, never decorative.** A pulse means working, a gold
  flash means the balance changed, a slide means a new entry arrived. There
  is no animation that does not report something.
- **The system never flatters itself.** A rule that blocks an action gets a
  red block of its own, and a ticket is only Resolved when the database says
  so. A dashboard that hid refusals would be prettier and worth much less.
- **Everything is honest about where it came from.** The timeline is the
  audit trail, the balance is `cash_accounts`, the approvals are real rows.
  There is no mock data anywhere in the frontend.

---

## Responsive behaviour

The grid collapses to one column below 1080px, ordering tickets above
approvals above the timeline — the same priority as the desktop reading
order. Cards stay full-width, the masthead wraps its cash plate under the
title, and touch targets stay at least 32px. `prefers-reduced-motion`
disables every animation on the page.

---

## Running it

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**, with the backend on port 8000. Verified
working from the `frontend/` folder.
