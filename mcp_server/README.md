# Campus Customs MCP Server

An MCP server that gives the Campus Customs agents read-only access to the
shop's operations data — inventory, pricing, vendors, invoices, leases and
cash.

## What it does

It exposes three tools, one for each of the three open tickets. Each tool
answers the question that ticket actually asks, pulling every figure from the
database. None of the tools write anything, move money, or place an order:
they report, and the agents decide.

## Which database it uses

`data/campus_customs_new.db` — the working copy made in Problem 2.

The supplied `data/campus_customs.db` is never opened. Keeping it pristine
means a run can always be reset by re-copying, and there is a clean reference
to diff against.

One rule is baked into the data layer: **dates are judged against
`desk.date_today` (2026-08-31), not the system clock.** The real date is well
past that, so a clock-based check would call everything overdue and reach the
wrong conclusions.

## The tools

Sixteen tools in five groups. Read tools report; write tools act, and every
one of them enforces a business rule in code before it does.

| group | tools |
| --- | --- |
| **Ticket-specific** | `check_order_fulfillment`, `check_rent_due`, `quote_bulk_discount` |
| **Reading the work** | `list_open_tickets`, `get_ticket` |
| **Money and vendors** | `get_cash_position`, `list_outstanding_invoices`, `check_vendor_status` |
| **Approvals** | `request_approval`, `list_pending_approvals` |
| **Acting on approval** | `record_payment`, `create_purchase_order` |
| **Communications** | `draft_customer_email`, `draft_vendor_message`, `list_drafts` |
| **Progress** | `update_ticket_status` |

### The original three

### `check_order_fulfillment(sku, size, qty=1)` — ticket 101

Can we fill this customer order today? Returns the quantity on hand for the
exact size, every other size carried, the cost and list price, and — when
stock is short — which vendors could restock it and whether any of them is
blocked by an unpaid invoice.

On ticket 101 it reports that `CC-TEE-WHITE` in size S is at qty 0, that M, L
and XL are available as alternatives, and that the only apparel vendor
(Bulldog Print Co) is blocked by invoice #501 for $840, three days overdue.

### `check_rent_due(lease_id=1, account="checking")` — ticket 102

What is owed on the lease, when, and can the shop cover it? Returns the rent
amount, days until due measured from the shop's date, whether cash covers it
and what would be left, and whether a payment has already been recorded.

On ticket 102: $2,400 to Elm City Properties, due 2026-09-02, two days out;
checking holds $3,400, leaving $1,000 afterwards. The reply always states that
payment needs human approval.

### `quote_bulk_discount(sku, size, qty, proposed_unit_price=None)` — ticket 103

Can we supply a bulk order, and at what price? Returns stock against the
requested quantity, the shortfall, cost and list price, the totals, and the
break-even floor. Pass a proposed price and it reports the discount
percentage, the resulting margin, and whether it still makes money.

On ticket 103: 8 navy hoodies in M against 20 requested, short 12; cost $22,
list $58, break-even at 62% off. A proposed $40 is 31% off and still clears
$360.

### Reading the work

**`list_open_tickets()`** — the inbox, for the Boss to see what needs doing.

**`get_ticket(ticket_id)`** — one ticket with its foreign keys already
resolved: the linked invoice (with days overdue), the linked lease (with days
until due), and the product with its stock across every size. One call
instead of four, which is the point.

### Money and vendors

**`get_cash_position(account)`** — balance, the total committed to pending or
approved requests, and `available_to_commit`, which is the number that
matters. Treating the raw balance as spendable is how two agents commit the
same dollars.

**`list_outstanding_invoices()`** — every unpaid bill with its days overdue,
measured against the shop's date.

**`check_vendor_status(vendor_id)`** — whether this vendor has unpaid
invoices, and so whether they can be ordered from at all.

### Approvals — the only way to spend money or change a price

**`request_approval(kind, amount, requested_by, reason, ...)`** — queues a
decision for a human. Kinds: `invoice_payment`, `rent_payment`,
`purchase_order`, `price_override`. It spends nothing. It refuses a request
beyond available cash, and refuses a duplicate of one already pending.

**`list_pending_approvals(status)`** — what is waiting on a person.

### Acting on an approval

**`record_payment(approval_id, account)`** — pays, debits the balance and
marks the invoice paid. **Refuses unless the approval exists and a human has
set it to `approved`.** Also refuses a second payment for the same thing.

**`create_purchase_order(approval_id, vendor_id, sku, qty, ...)`** — places a
restock order. Requires an approved `purchase_order` approval, and
**re-checks the vendor's unpaid invoices at order time** rather than trusting
whenever the agent last looked.

### Communications — drafts only

**`draft_customer_email(...)`** and **`draft_vendor_message(...)`** save text
for a person to review. **There is no send function anywhere in this
codebase**, which is how the "drafts only" rule is enforced: not by asking
the agent nicely, but by there being no other option.

**`list_drafts(ticket_id)`** — what has been written.

### Progress

**`update_ticket_status(ticket_id, status, note, updated_by)`** — moves a
ticket to `open`, `in_progress`, `waiting_approval`, `resolved` or `blocked`,
appending a stamped note rather than replacing the existing ones.

## Tables added to the working copy

The supplied database has nowhere to record a pending approval, a draft, or a
purchase order — but the rules require all three. Three tables are added to
`campus_customs_new.db` by `schema.py` on server start (idempotent):

| table | holds |
| --- | --- |
| `approvals` | requests awaiting a human decision, and the decision |
| `drafts` | customer emails and vendor messages, never sent |
| `purchase_orders` | restock orders, each tied to its approving approval |

The nine supplied tables are not altered, and `campus_customs.db` is never
opened.

## Design notes

- **Nothing is invented.** Every figure is read from the database or computed
  from it by plain arithmetic. Where the database has no answer — an unknown
  sku, a missing lease — the tool says so or raises a clear error rather than
  guessing.
- **A zero-quantity row is not a missing row.** The tools distinguish "we do
  not carry this" from "we carry it and have none", because the right reply
  to a customer differs.
- **Vendor blocking is computed, not assumed.** A vendor is blocked when the
  database holds any invoice for them that is not `paid`. The status column
  is free text, so the check is "not paid" rather than "equals open".
- **Approval is surfaced, not decided.** The rent and discount tools both
  return `requires_human_approval: true`. They never act on it.

## A note on FastMCP

The assignment asks for FastMCP. The installed SDK is `mcp` 2.2.0, in which
**FastMCP was renamed to `MCPServer`** — the same decorator-based API under a
new name. Importing `mcp.server.fastmcp` fails on this version with an error
pointing at the rename, so `MCPServer` is the correct successor and is what
this server uses.

## Layout

| file | what it holds |
| --- | --- |
| `server.py` | the three tools and the `MCPServer` instance |
| `db.py` | every SQL query, all parameterised; the `desk.date_today` rule |
| `models.py` | typed return shapes, so clients get structured output |

## Running it

Not required yet — the server is built but not wired to a client.

```bash
python -m mcp_server.server
```

It speaks MCP over stdio.
