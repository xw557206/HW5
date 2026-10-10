# Campus Customs Multi-Agent System — Harness

Working notes on how the system is built. Written as the work happens and
extended with each problem.

---

# Problem 2 — The database

## The working copy

`data/campus_customs.db` is the supplied file and is **never written to**.
Everything from here on runs against `data/campus_customs_new.db`, a
byte-for-byte copy (same SHA-256, `PRAGMA integrity_check` → `ok`, all nine
row counts matching).

Keeping the original untouched means any run can be reset by re-copying, and
there is always a clean reference to diff against when checking what the
agents changed.

## Tables at a glance

Nine tables, all small. The whole shop fits on one screen, which means every
agent decision can be checked by hand.

| table | rows | primary key |
| --- | --- | --- |
| `desk` | 1 | — |
| `tickets` | 3 | `id` |
| `inventory` | 10 | `(sku, size)` |
| `pricing` | 4 | `sku` |
| `vendors` | 3 | `id` |
| `invoices` | 1 | `id` |
| `leases` | 1 | `id` |
| `cash_accounts` | 1 | `name` |
| `payments` | 0 | `id` |

Three foreign keys are declared: `tickets.invoice_id → invoices.id`,
`tickets.lease_id → leases.id`, and `invoices.vendor_id → vendors.id`.

---

## Each table and how the agents use it

### `desk` — what day it is

| field | meaning |
| --- | --- |
| `date_today` | `2026-08-31` — the shop's current date |
| `notes` | free text, currently empty |

**How agents use it.** Every date question starts here. "Is this invoice
overdue?" and "when is rent due?" are answered against `date_today`, **not**
the computer's clock. This matters: the real date is well past 2026-08-31, so
an agent using the system clock would think everything is massively overdue
and would reach different conclusions. This is the first thing any agent
reads.

### `tickets` — the work to be done

| field | meaning |
| --- | --- |
| `id` | ticket number |
| `type` | `customer_order`, `rent_notice`, `price_override` |
| `requester` | who asked |
| `subject` | one-line summary |
| `sku`, `size`, `qty` | the product involved, when there is one |
| `lease_id` | links to `leases` for rent tickets |
| `invoice_id` | links to `invoices` when a bill is involved |
| `status` | `open` for all three |
| `notes` | the request in plain words |
| `created_at` | timestamp, all 2026-08-31 |

**How agents use it.** This is the inbox. The Boss agent reads `type` to
decide who should handle a ticket, and uses `sku`/`lease_id`/`invoice_id` to
know which other tables to pull in. The specialist agents write back to
`status` as work progresses.

### `inventory` — what is on the shelf

| field | meaning |
| --- | --- |
| `sku`, `size` | together, the primary key |
| `name` | the product's display name |
| `qty` | units on hand |
| `location` | aisle |

**How agents use it.** The Inventory agent checks `qty` for the exact
`(sku, size)` on a ticket before promising anything. A row existing does not
mean stock exists — two rows sit at `qty = 0`. Stock is tracked per size, so
"we have hoodies" is never a sufficient answer to "do you have a medium?".

### `pricing` — cost and list price

| field | meaning |
| --- | --- |
| `sku` | one row per product (all four covered) |
| `unit_cost` | what the shop pays |
| `list_price` | what the shop charges |

**How agents use it.** Needed for the discount ticket. `unit_cost` is the
floor — a discount that drops below it sells at a loss. It also prices any
restock: 12 hoodies at $22 cost is $264.

### `vendors` — who can supply things

| field | meaning |
| --- | --- |
| `id`, `name` | vendor identity |
| `specialty` | what they supply |
| `lead_days` | how long delivery takes |

**How agents use it.** Two checks before ordering: does the specialty match
what is needed, and does this vendor have unpaid invoices? `lead_days` sets
the promise made to a customer — a 5-day lead cannot fill a same-week order.

> **Careful:** vendor 2 is **Elm City Gifts** and the landlord on the lease is
> **Elm City Properties**. Different organisations with similar names. An
> agent must not pay one thinking it is the other.

### `invoices` — bills the shop owes

| field | meaning |
| --- | --- |
| `id` | invoice number |
| `vendor_id` | who is owed |
| `amount` | how much |
| `due_date` | when due |
| `status` | `open` on the only row |
| `description` | what it covers |

**How agents use it.** Two jobs. The Accounting agent finds overdue bills by
comparing `due_date` to `desk.date_today`. And any agent wanting to place an
order must check here first — an open invoice blocks new orders to that
vendor.

### `leases` — the shop's rent

| field | meaning |
| --- | --- |
| `id`, `space_name`, `landlord` | which space, and who the landlord is |
| `monthly_rent` | amount due |
| `next_due` | next payment date |
| `notes` | free text, empty |

**How agents use it.** The Facilities agent handles rent tickets from here,
comparing `next_due` to `desk.date_today`. Rent is the largest single number
in the dataset, so it dominates any cash decision.

### `cash_accounts` — what the shop can spend

| field | meaning |
| --- | --- |
| `name` | `checking`, the only account |
| `balance` | `3400.00` |
| `date` | `2026-08-31`, matching the desk date |

**How agents use it.** The spending ceiling. Nothing may be committed beyond
this balance, and because there is only one account, every payment competes
with every other.

### `payments` — the record of money sent

| field | meaning |
| --- | --- |
| `id` | payment number |
| `kind` | what sort of payment (invoice, rent) |
| `ref_id` | the invoice or lease it settles |
| `amount` | how much |
| `account` | which account it came from |
| `paid_at` | when |
| `approved_by` | **who approved it** |

**How agents use it.** Starts empty — nothing has been paid yet. A row here is
written only after a human approves through the dashboard.

`approved_by` is `NOT NULL`, which is worth noticing: the schema itself makes
an unapproved payment impossible to record. The human-approval rule is not
only a prompt instruction, it is enforceable in the data model.

---

## The three open tickets, and how they interlock

All three are `open` and all three were created on 2026-08-31, the desk date.
They are not independent — they contend for the same cash and the same vendor.

### Ticket 101 — customer order, Tauhid Zaman

Wants one **Classic Bulldog Tee**, `CC-TEE-WHITE`, **size S**.

- Inventory: size S is at **qty 0**. Out of stock.
- Other sizes exist — M 5, L 3, XL 2 — but not the one asked for.
- The ticket carries `invoice_id = 501`. That invoice is a rush reprint of
  **this exact SKU and size**, for **$840**, owed to **Bulldog Print Co**.
- Invoice 501 is due 2026-08-28 and still `open` — **3 days overdue**.
- Bulldog Print Co is the only **apparel** vendor, so it is the only one who
  could reprint the tee. The unpaid-invoice rule **blocks ordering from them**
  until the $840 is settled.
- Even once unblocked, their lead time is 5 days.

### Ticket 102 — rent notice, Elm City Properties

Rent on the Chapel Street shop.

- Lease 1: **$2,400**, next due **2026-09-02** — **2 days away**, which
  matches the note on the ticket.
- Affordable on its own against a $3,400 balance.
- Requires human approval before any payment row is written.

### Ticket 103 — price override, Yale AI Club

Wants **20 navy hoodies in size M** with a bulk discount.

- Inventory: size M is at **qty 8**. **Short by 12.**
- Other sizes are stocked — S 4, M 8, L 14, XL 6, 32 total — but they asked
  for M.
- Pricing: cost $22, list $58. Twenty at list is $1,160; selling at cost would
  be $440. Any discount has to stay above $22 a unit.
- Covering the 12-unit shortfall means an apparel reprint — which again means
  Bulldog Print Co, which is again blocked by invoice 501.

### What ties them together

**Invoice 501 is the keystone.** It is three days overdue, and it blocks the
only apparel vendor in the dataset. Both the tee for ticket 101 and the hoodie
shortfall for ticket 103 need that vendor. Neither product ticket can be fully
resolved by ordering until the $840 is paid.

**The cash is deliberately tight.**

| | amount |
| --- | --- |
| checking balance | $3,400.00 |
| invoice 501 | −$840.00 |
| rent (lease 1) | −$2,400.00 |
| **left over** | **$160.00** |

Both obligations fit, with $160 to spare. But there is no room left to also
fund a restock — 12 hoodies at cost would be $264. So the agents cannot simply
approve everything; they have to sequence, and some requests will need a
partial answer or a draft reply rather than a purchase.

### Vendor standing

| vendor | specialty | lead | open invoices | can order? |
| --- | --- | --- | --- | --- |
| 1 Bulldog Print Co | apparel reprint | 5 days | 1 ($840) | **blocked** |
| 2 Elm City Gifts | mugs and small goods | 3 days | none | yes |
| 3 QuickShip CT | local courier | 1 day | none | yes |

The two orderable vendors cannot supply apparel, which is what both product
tickets need. That is the squeeze the system has to reason about.

---

## Things to watch out for

Noted now so they do not become bugs later.

1. **Use `desk.date_today`, never the system clock.** The stored date is
   2026-08-31. Real "now" is later, which would make every date comparison
   wrong.
2. **Two different "Elm City" parties.** Elm City Gifts is a vendor; Elm City
   Properties is the landlord. Matching on name alone will confuse them — join
   on id.
3. **A stock row at zero is still a row.** Check `qty`, not existence.
   `CC-TEE-WHITE/S` and `CC-MUG-CREST/OS` are both at zero.
4. **Stock is per size.** Totals across sizes never answer a size question.
5. **One cash account.** Every payment competes with every other; a balance
   check has to account for what is already committed in the same run, not
   just the stored number.
6. **`payments.approved_by` is `NOT NULL`.** Lean on that — it is a real
   constraint, not a convention.
7. **`invoices.status` is free text.** The one row says `open`. Treat anything
   that is not `paid` as outstanding rather than matching only `open`.

---

# Problem 3 — The MCP server

Built in `mcp_server/`, reading `data/campus_customs_new.db`. Three tools, one
per open ticket. All read-only: they report, the agents decide.

## The three tools

| tool | tables used | ticket | why it helps |
| --- | --- | --- | --- |
| `check_order_fulfillment(sku, size, qty)` | `inventory`, `pricing`, `vendors`, `invoices`, `desk` | **101** — customer order | The customer wants a size that is at qty 0. The tool reports the shortfall, lists the sizes that *are* stocked so an alternative can be offered, and checks whether any apparel vendor could restock — which surfaces that the only one is blocked by an unpaid invoice. Without this the agent would promise a tee it cannot get. |
| `check_rent_due(lease_id, account)` | `leases`, `cash_accounts`, `payments`, `desk` | **102** — rent notice | Turns "rent is due" into numbers: how much, how many days away measured from the shop's own date, whether cash covers it, what is left afterwards, and whether it has already been paid. It also returns `requires_human_approval: true`, so the agent cannot treat paying as routine. |
| `quote_bulk_discount(sku, size, qty, proposed_unit_price)` | `pricing`, `inventory`, `desk` | **103** — bulk price override | A discount request needs two facts the agent cannot guess: can we supply 20, and how low can the price go? The tool gives the shortfall and the break-even floor from `unit_cost`, then scores any proposed price for margin. It prevents both over-promising stock and discounting below cost. |

## What each tool returned on its own ticket

Run against the working copy, so these are the real values.

**Ticket 101** — `check_order_fulfillment("CC-TEE-WHITE", "S", 1)`

```
qty_on_hand 0 | can_fulfill_now False | shortfall 1
other sizes  {S: 0, M: 5, L: 3, XL: 2}
vendor       Bulldog Print Co -> can_order False
             "1 unpaid invoice totalling $840.00 (#501 due 2026-08-28).
              No new orders until settled."
any_vendor_available False
```

**Ticket 102** — `check_rent_due(1)`

```
rent $2,400.00 | due 2026-09-02 | days_until_due 2 | is_overdue False
balance $3,400.00 | affordable True | balance_after_payment $1,000.00
already_paid False | requires_human_approval True
```

**Ticket 103** — `quote_bulk_discount("CC-HOOD-NAVY", "M", 20, 40.00)`

```
on hand 8 of 20 | shortfall 12 | can_fill_from_stock False
cost $22.00 | list $58.00 | list_total $1,160.00 | margin_at_list $720.00
break-even floor $22.00/unit = 62.1% off list
proposed $40.00 -> 31.0% off, $800.00 total, $360.00 margin, profitable True
```

## Design decisions

- **One tool per ticket, not one tool per table.** A tool that answers the
  question the ticket asks keeps the agent from having to stitch four lookups
  together and get the business rule wrong in the middle.
- **Nothing is invented.** Every field is read from the database or computed
  from it by arithmetic. Unknown sku, missing lease, zero quantity — each
  returns a stated fact or raises a clear error.
- **"Not carried" and "carried but empty" are different answers.** The tools
  distinguish them, because what you tell the customer differs.
- **Vendor blocking is derived, not hardcoded.** A vendor is blocked when any
  invoice for them is not `paid`. Written as "not paid" rather than "equals
  open", since the column is free text.
- **Approval is reported, never decided.** Both the rent and discount tools
  return `requires_human_approval: true` and take no action.

## Library note

The assignment specifies FastMCP. The installed SDK is `mcp` 2.2.0, where
**FastMCP was renamed `MCPServer`** — same decorator API, new name. Importing
`mcp.server.fastmcp` fails on this version with an error naming the rename, so
`MCPServer` is the correct successor and is what the server uses.

## Verification

| check | result |
| --- | --- |
| tools register with the server | 3 of 3, with correct parameter names |
| each tool on its own ticket | matches the Problem 2 analysis exactly |
| unknown sku | "CC-NOPE is not in the catalogue, so nothing can be promised." |
| carried but zero (`CC-MUG-CREST`) | reported out of stock, and correctly suggested Elm City Gifts, who have no unpaid invoices |
| in-stock case (`CC-HAT-BLUE`, 40 on hand) | `can_fulfill_now True` |
| below-cost proposal ($15 vs $22 cost) | `proposed_is_profitable False`, margin −$140 |
| no price proposed | proposal fields stay `None` rather than defaulting |
| bad lease id / unknown sku / qty 0 | clear `ValueError` naming the problem |
| original database | SHA-256 unchanged — never opened |

---

# Problem 4 — Connecting the server and testing the tools

## The connection

`.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "campus-customs": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": { "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

`PYTHONUTF8` is there because the tool summaries contain en-dashes and dollar
signs; without it the Windows console codepage mangles them. `PYTHONUNBUFFERED`
keeps stdio responses from sitting in a buffer.

## How the tools were tested

`scripts/mcp_smoke_test.py`, re-runnable:

```bash
python scripts/mcp_smoke_test.py
```

Two decisions make this a real test rather than a formality:

1. **It goes over the wire.** The script reads `.mcp.json`, launches the
   server as a subprocess with that exact command, performs the MCP
   handshake, and calls the tools through `ClientSession`. It never imports
   the tool functions. So it tests the *connection*, not just the Python.
2. **Every number is re-checked against the database.** After each call the
   script runs independent `sqlite3` queries and compares them field by field
   with what the tool returned. A tool that invented a value fails here
   instead of looking plausible.

## Results

All three tools passed: **40 of 40 value checks matched the database.**

### Ticket 101 — `check_order_fulfillment` — 11/11

> **Prompt:** Ticket 101: Tauhid Zaman wants one Classic Bulldog Tee
> (CC-TEE-WHITE) in size S. Can we fill this order today, and if not, who
> could restock it?

Arguments: `{"sku": "CC-TEE-WHITE", "size": "S", "qty": 1}`

| returned | database |
| --- | --- |
| `qty_on_hand` 0 | `inventory` S row = 0 |
| `can_fulfill_now` false | — |
| `shortfall` 1 | 1 requested − 0 on hand |
| sizes `{S:0, M:5, L:3, XL:2}` | matches all four `inventory` rows |
| `unit_cost` 8.0 | `pricing` |
| blocked vendor "Bulldog Print Co" | the only apparel vendor with an unpaid invoice |
| outstanding total 840.0 | `invoices` #501 |
| `any_vendor_available` false | — |
| `shop_date` 2026-08-31 | `desk.date_today` |

### Ticket 102 — `check_rent_due` — 13/13

> **Prompt:** Ticket 102: Elm City Properties says shop rent is due in 2 days.
> How much is owed on the lease, when exactly, and can we afford it?

Arguments: `{"lease_id": 1, "account": "checking"}`

| returned | database |
| --- | --- |
| `monthly_rent` 2400.0, `next_due` 2026-09-02 | `leases` |
| landlord "Elm City Properties", space "Chapel Street shop" | `leases` |
| `days_until_due` 2 | computed from `desk.date_today` |
| `is_overdue` false, `is_due_soon` true | — |
| `cash_balance` 3400.0 | `cash_accounts` |
| `affordable` true, `balance_after_payment` 1000.0 | 3400 − 2400 |
| `already_paid` false | `payments` has no rent row |
| `requires_human_approval` true | — |

### Ticket 103 — `quote_bulk_discount` — 16/16

> **Prompt:** Ticket 103: the Yale AI Club wants 20 navy hoodies
> (CC-HOOD-NAVY) in size M at a bulk discount. Can we supply them, and would
> $40 per unit still make money?

Arguments: `{"sku": "CC-HOOD-NAVY", "size": "M", "qty": 20, "proposed_unit_price": 40.0}`

| returned | database |
| --- | --- |
| `qty_on_hand` 8, `shortfall` 12 | `inventory` M row |
| `can_fill_from_stock` false | — |
| `unit_cost` 22.0, `list_price` 58.0 | `pricing` |
| `list_total` 1160.0, `cost_total` 440.0 | 20 × each |
| `margin_at_list` 720.0 | 1160 − 440 |
| `min_unit_price` 22.0, `max_discount_pct_at_cost` 62.1 | from `pricing` |
| `proposed_total` 800.0, `proposed_margin` 360.0 | 20 × 40, minus cost |
| `proposed_discount_pct` 31.0, `proposed_is_profitable` true | 40 > 22 |

## Proving the test can fail

A passing test is only meaningful if it can fail. `stock_for()` was
temporarily patched to return `qty = 99` instead of the real value, and the
smoke test was re-run:

```
ticket 101  fail: 4/11 checks matched
   MISMATCH qty_on_hand matches inventory: tool=99 db=0
   MISMATCH can_fulfill_now is False: tool=True db=False
   MISMATCH shortfall: tool=0 db=1
   ... and the whole vendor-blocking chain collapsed
ticket 103  fail: 13/16 checks matched
   MISMATCH qty_on_hand matches inventory: tool=99 db=8
```

The sabotage was reverted and the clean run restored to 40/40. This confirms
the checks compare against the database rather than against the tool's own
output.

## Issues found and fixed

Both were in the test script, not the server, and both came from the same
cause — `mcp` 2.x renamed several camelCase attributes to snake_case:

| error | fix |
| --- | --- |
| `'InitializeResult' object has no attribute 'serverInfo'` | → `server_info` |
| `'CallToolResult' object has no attribute 'isError'` | → `is_error` |

(An earlier probe hit the same thing with `Tool.inputSchema` → `input_schema`.)
The server itself needed no changes.

## Record

`output/mcp_smoke.json` holds the full run: the prompt, tool, arguments,
complete returned object, and every individual check with the tool's value
beside the database's value.

Both database files are byte-identical to before the run — the tools are
read-only, as intended.

---

# Problem 5 — The agent team

Five PydanticAI agents in `backend/`, all on **gpt-6-luna through Portkey**,
all reading the shop through the MCP server.

## Architecture

```
          ticket
            |
      route_ticket()          <- no model call; the ticket type decides
            |
      specialist agent        <- 1 model run, may ask a colleague
            |
      Boss review             <- 1 model run
            |
      TicketOutcome  +  output/audit_trail.json
```

**The backend holds no database connection.** `backend/` contains no SQL and
never opens a `.db` file. Everything — stock, cash, invoices, rent, tickets —
arrives through the MCP server. That is deliberate: the business rules live
inside the MCP tools, so a backend that could reach the database directly
would be a way to walk straight past them.

## The five agents

| agent | owns | MCP tools it uses | tables behind those tools |
| --- | --- | --- | --- |
| **Boss** | triage, review, cross-ticket priorities | `list_open_tickets`, `get_ticket`, `get_cash_position`, `list_pending_approvals`, `update_ticket_status` | `tickets`, `leases`, `invoices`, `inventory`, `pricing`, `cash_accounts`, `approvals`, `desk` |
| **Inventory** | stock, restocking, vendors, purchase orders | `check_order_fulfillment`, `get_ticket`, `check_vendor_status`, `get_cash_position`, `request_approval`, `create_purchase_order`, `draft_vendor_message`, `update_ticket_status` | `inventory`, `pricing`, `vendors`, `invoices`, `purchase_orders`, `approvals`, `drafts`, `cash_accounts`, `desk` |
| **Accounting** | invoices, cash, payments, pricing, discounts | `list_outstanding_invoices`, `get_cash_position`, `check_vendor_status`, `quote_bulk_discount`, `get_ticket`, `request_approval`, `record_payment`, `draft_vendor_message`, `update_ticket_status` | `invoices`, `vendors`, `cash_accounts`, `payments`, `pricing`, `inventory`, `approvals`, `drafts`, `desk` |
| **Facilities** | the lease, rent, the premises | `check_rent_due`, `get_ticket`, `get_cash_position`, `request_approval`, `record_payment`, `draft_vendor_message`, `update_ticket_status` | `leases`, `cash_accounts`, `payments`, `approvals`, `drafts`, `desk` |
| **Customer Service** | anything a customer reads | `get_ticket`, `check_order_fulfillment`, `quote_bulk_discount`, `draft_customer_email`, `update_ticket_status` | `tickets`, `inventory`, `pricing`, `drafts`, `desk` |

All sixteen tools are available to all five agents; the table lists what each
one's prompt directs it to use.

## How agents talk to each other

Each agent gets an `ask_<colleague>` tool per permitted colleague. The graph
is deliberately narrow — an agent with four colleagues delegates instead of
using its own tools:

| agent | can ask |
| --- | --- |
| Boss | inventory, accounting, facilities, customer_service |
| Inventory | accounting, customer_service |
| Accounting | inventory, facilities |
| Facilities | accounting |
| Customer Service | inventory, accounting |

Every hop raises `TeamDeps.depth`. At `MAX_DELEGATION_DEPTH` (2) the tool
**refuses and returns a message** instead of running another agent, so two
agents cannot consult each other in circles. The Boss's review run starts at
the limit, so a review cannot spawn a second round of investigation.

## Safety rules

Five rules, stated in the prompts and — the part that matters — enforced in
`mcp_server/ops.py`. A prompt rule is a request to a language model; a check
in code is a guarantee.

| rule | prompt | code |
| --- | --- | --- |
| No payment without human approval | shared rules §3 | `record_payment` refuses unless an `approvals` row is `approved` |
| No ordering from a vendor with unpaid invoices | shared rules §4 | `create_purchase_order` re-queries unpaid invoices at order time |
| Never spend more cash than available | shared rules §5 | `request_approval` checks `available_to_commit`, not `balance` |
| Use the shop's stored date | shared rules §1 | `db.today()` reads `desk.date_today`; no tool touches the clock |
| Communications are drafts only | shared rules §6 | **there is no send function anywhere in the codebase** |

Verified by attempting each violation directly:

```
BLOCKED  record_payment on a nonexistent approval
         -> "No approval #999 exists. Request one first."
BLOCKED  record_payment on a PENDING approval
         -> "Approval #1 is 'pending', not 'approved'. A human must approve it first."
BLOCKED  create_purchase_order from blocked vendor 1
         -> "Cannot order from Bulldog Print Co: 1 unpaid invoice totalling $840.00 (#501)."
BLOCKED  request_approval for $99,999
         -> "only $2,296.00 is available (balance $3,400.00 less $1,104.00 committed)."
BLOCKED  duplicate pending request for the same invoice
         -> "A pending invoice_payment request for ref 501 already exists (#1)."
ALLOWED  save_draft -> draft #1, status 'draft', sent=False
         any send function in ops.py? NONE
```

## Approval requirements

Four things need a human, and nothing else moves money or changes a price:

| kind | raised by | what it authorises |
| --- | --- | --- |
| `invoice_payment` | Accounting | paying a vendor invoice |
| `rent_payment` | Facilities | paying rent on a lease |
| `purchase_order` | Inventory | placing a restock order |
| `price_override` | Accounting | changing a price for a bulk request |

The flow is: agent calls `request_approval` → row written as `pending` →
**agent stops** → a human decides on the dashboard → only then can
`record_payment` or `create_purchase_order` succeed.

Note that `payments.approved_by` is `NOT NULL` in the supplied schema, so an
unapproved payment is not merely discouraged — it cannot be recorded.

## Avoiding unnecessary AI calls

The expensive thing here is model calls, so the design spends them only where
judgement is actually required.

1. **Routing is code, not a model call.** `route_ticket()` reads the ticket's
   `type` column and returns the owning agent. The database already says what
   a ticket is; paying a model to rediscover it is waste. Only an
   unrecognised type reaches the Boss for triage.
2. **Two model runs per ticket, not five.** One specialist plus one Boss
   review. The other three agents are only woken if the specialist genuinely
   needs them.
3. **A narrow delegation graph.** Each specialist can reach one or two
   colleagues, not all four, which removes the easy option of delegating
   instead of working.
4. **A hard delegation ceiling.** Depth 2, enforced in the tool rather than
   requested in the prompt.
5. **Composite tools.** `get_ticket` returns the ticket with its invoice,
   lease, product and stock already resolved — one call where a naive design
   would make four, each costing a model round-trip.
6. **Rules enforced in code.** A blocked vendor or an unapproved payment is
   refused by the tool instantly. No model call is spent deciding whether a
   rule applies.
7. **One shared toolset.** All five agents share a single MCP connection, so
   the server starts once and the tool list is fetched once (`cache_tools`).
8. **Usage limits.** 12 requests and 20 tool calls per agent run; a confused
   loop stops instead of spending.

## Audit trail

`output/audit_trail.json`, append-only. One entry per agent run, including
runs that fail.

Each entry: `entry_id`, `run_id`, `agent`, `ticket_id`, `task`,
`delegation_depth`, timestamps, `iterations`, `steps[]` (each with the tool,
clipped arguments, a clipped result and a status), `tools_used`,
**`rule_refusals`**, `delegated_to`, `status`, `stop_reason`, `usage`.

`rule_refusals` is the interesting column: it is where a business rule
refusing an agent shows up, so "the rules worked" is visible in the record
rather than inferred.

Not recorded: no secrets, no reasoning content (a boolean only notes that
reasoning occurred), no unbounded blobs — arguments clip at 220 characters
and results at 320. Writes go through a lock to a temp file that is then
renamed, and an unreadable trail is preserved as `.corrupt-<ts>.json` rather
than overwritten.

## Verification

`scripts/offline_team_check.py` — **21/21 checks passed, with no model
calls** (PydanticAI's `TestModel` stands in):

| group | result |
| --- | --- |
| routing | all 8 cases correct, including three unknown-type fallbacks and the Boss catch-all |
| delegation graph | each agent has exactly its permitted `ask_*` tools |
| depth guard | at depth 2 the tool refuses and names the limit instead of recursing |
| audit append | one run → exactly one new entry, with the right agent and ticket |
| append-only | a second run leaves the first entry's `entry_id` untouched |
| MCP reach | all 16 tools visible to all five agents |

**Not yet done: a live end-to-end run.** The agents have not been run against
the real model, so the quality of their judgement is unverified — only the
wiring is. See the note in `AI_prompts.md`.

---

# Problem 7 — Backend routes

`backend/main.py`, FastAPI. Six routes plus a health check, ready for the
React dashboard.

```bash
uvicorn backend.main:app --reload --port 8000
```

## The routes

| method | path | does |
| --- | --- | --- |
| `GET` | `/tickets` | the three tickets, descriptions and open/resolved |
| `POST` | `/tickets/{id}/run` | runs the agent team on one ticket |
| `GET` | `/events` | recent agent activity from the audit trail |
| `POST` | `/approvals/{id}` | a person approves or rejects a request |
| `GET` | `/cash` | the checking balance and what is committed |
| `POST` | `/reset` | restores the working database |
| `GET` | `/health` | MCP connection, tool count, shop date |

Every response carries `ok` and `status`, so the dashboard branches on two
fields rather than inferring from an HTTP code. Failures all return the same
`ErrorResponse` shape.

`RunStatus` is one of `resolved`, `needs_approval`, `blocked`, `in_progress`
or `failed` — which answers the dashboard's actual question: is this done, is
it waiting on me, or is it stuck?

## No database access in the backend

`backend/main.py` has no `sqlite3` import and no `.db` path. Every business
figure comes through `mcp()`, a single helper that wraps
`direct_call_tool`. That is the whole point: the business rules live inside
the MCP tools, so a backend that could reach the database directly would be a
way around them.

Even `POST /reset`, which copies a file, goes through the MCP tool
`reset_working_database` rather than copying from the backend — so every
database operation stays in one place.

## Two tools the agents cannot see

Adding `decide_approval` created a hole: an agent that can approve its own
request makes the approval rule decorative. Same for a reset — an agent that
can restore the database can erase the record of what it did.

So `backend/mcp_client.py` defines:

```python
HUMAN_ONLY_TOOLS = {"decide_approval", "reset_working_database"}

def agent_toolset(toolset):
    return toolset.filtered(lambda ctx, tool: tool.name not in HUMAN_ONLY_TOOLS)
```

The API uses the full toolset; the agents get the filtered view. The
capability is **absent** for agents, not merely discouraged.

## How an approval actually executes

`POST /approvals/{id}` is the only place money moves, and the order of
operations matters:

1. **Fetch the approval.** Missing → `404`.
2. **Reject a second decision.** Already approved or rejected → `409`. This
   is what makes double payment impossible.
3. **If rejecting** — record it, move nothing, report the unchanged balance.
4. **If approving** — check affordability *before* recording the decision.
   If the amount exceeds the balance the decision is **not recorded at all**,
   so the request stays pending rather than being half-approved.
5. **Record the decision**, then execute through `record_payment` or
   `create_purchase_order`.
6. **The MCP tool re-checks every rule at execution time.** An approval
   granted earlier cannot force through a payment the shop can no longer
   afford, or an order to a vendor that has since become blocked.

Step 6 is why the vendor test below passes: a human approved the purchase
order and it was still refused.

## Testing

`scripts/api_check.py` — **39/39 checks passed**. Uses FastAPI's in-process
test client, so no server is needed. `POST /tickets/{id}/run` is tested only
for its guard rails, so **no model call is made**.

| group | result |
| --- | --- |
| `/health` | MCP connected, 19 tools, shop date 2026-08-31 |
| `/tickets` | 3 tickets, correct ids, all open, descriptions and FK links present |
| `/cash` | $3,400.00 balance, $0 committed, $3,400 available |
| `/tickets/999/run` | `404`, error names the real tickets |
| `/events` | returns the recorded entries |
| **rejection** | status `rejected`, nothing executed, **balance unchanged** |
| **double decision** | `409` — "already rejected … cannot be decided twice" |
| **missing approval** | `404` |
| **unaffordable request** | refused at request time by the cash guard |
| **approved payment** | executed once, balance $3,400 → $2,560, exactly $840 |
| **repeat payment** | `409` — no double payment |
| **blocked vendor** | **approved by a human and still refused**: "Cannot order from Bulldog Print Co: 1 unpaid invoice(s) totalling $840.00 (#501)" |
| `/reset` | balance restored to $3,400, approvals and payments cleared, tickets intact, audit trail kept |

The blocked-vendor row is the one worth reading twice. A person approved the
order and the system still said no, because the rule is re-checked at
execution rather than trusted from when the agent asked.

## Issues found and fixed

| problem | cause | fix |
| --- | --- | --- |
| Test deadlocked on `request_approval` | the helper reached into the app's MCP connection from a different event loop | seed approvals via `mcp_server.ops` directly — test setup only; the routes under test still go through MCP |
| Rule messages replaced by "Error executing tool X" | MCP masks a generic exception | raise `ToolError` instead of `ValueError` in the tools; the message now reaches the client intact |
| Error classification was keyword-matching | fragile | `ModelRetry` → `400` (a rule said no), anything else → `503` (connection) |
| `/health` reported 19 tools, test expected 18 | my own stale count | corrected the expectation — 16 from Problem 5 plus 3 new |

## Reset behaviour

`POST /reset` restores `campus_customs_new.db` from the untouched original
and clears approvals, drafts, purchase orders and payments.

**The audit trail is kept by default.** Resetting the shop does not unhappen
what the agents did, and the trail is the record of it. `?keep_audit=false`
archives it to a timestamped file — moved aside, never deleted.

---

# API route reference

Every endpoint in `backend/main.py`, one per line. This is how the React
dashboard talks to the backend.

Base URL in development: `http://127.0.0.1:8000`

### Routes

**`GET /tickets`** — Returns tickets 101, 102 and 103 with their
descriptions, type, requester and whether each is still open. Optional
`?include_closed=false` hides resolved ones.

**`POST /tickets/{ticket_id}/run`** — Runs the agent team on one ticket. The
Boss routes it, a specialist works it, the Boss reviews. Returns the outcome,
the agents involved, the MCP tools they called, and any requests now waiting
for human approval. Returns `404` for an unknown ticket.

**`GET /events`** — Recent agent activity from `output/audit_trail.json`:
agent name, ticket id, what it did, which MCP tools it called, timestamps,
and any point where a business rule refused it. Newest first. Optional
`?limit=50`, `?run_id=…`, `?ticket_id=…`.

**`POST /approvals/{request_id}`** — A person approves or rejects a pending
payment, purchase order or price override. Body: `decision`
(`approved`/`rejected`), `decided_by`, optional `note` and `account`. This is
the only route where money moves, and it happens only after the decision is
recorded.

**`GET /cash`** — The checking account balance, how much is already committed
to open requests, and what is genuinely available to spend. Optional
`?account=checking`.

**`POST /reset`** — Restores `data/campus_customs_new.db` from the untouched
original and clears approvals, drafts, purchase orders and payments. The
audit trail is kept; `?keep_audit=false` archives it to a timestamped file
instead.

**`GET /health`** — Whether the MCP server is reachable, how many tools it
exposes, the shop's current date, and whether the agents are configured.
Useful as a first check when the dashboard shows nothing.

### Notes for the frontend

- Every response includes `ok` (boolean) and, where relevant, `status`, so
  the dashboard can branch on those rather than on the HTTP code.
- `POST /tickets/{id}/run` returns `status` as one of `resolved`,
  `needs_approval`, `blocked`, `in_progress` or `failed`.
- `POST /approvals/{id}` returns `status` as `executed`, `rejected` or
  `blocked`, with `executed: true` only when money actually moved.
- Errors always come back in the same shape:
  `{ "ok": false, "status": "error", "error": "...", "detail": "..." }`.
- Common codes: `400` a business rule refused the request, `404` unknown
  ticket or approval, `409` already decided, `503` the MCP server is
  unreachable.
- CORS is enabled for `localhost:5173` and `localhost:3000`.
- FastAPI also serves `/docs` and `/openapi.json` automatically.

---

# Problem 8 — The React dashboard

`frontend/`, Vite + React + TypeScript. Talks only to the Problem 7 API.

## Running it

Two terminals, from the project root:

```bash
uvicorn backend.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**.

The dashboard calls `/api/...` and Vite proxies to FastAPI, so there is no
CORS round-trip in development and no hostname baked into the build. If the
backend is on another port: `BACKEND_PORT=8001 npm run dev`.

## Files

| file | holds |
| --- | --- |
| `src/types.ts` | mirrors the Pydantic models, so a backend change lands in one place |
| `src/api.ts` | the typed client and `ApiError`; every call goes through here |
| `src/agents.tsx` | each agent's colour, initials and role — the visual identity |
| `src/components.tsx` | crest, ticket card, timeline, approval card, toasts, modal |
| `src/App.tsx` | state, polling, and the three actions (run, decide, reset) |
| `src/index.css` | the Yale design tokens, matching `desk_tickets.html` |

## What it does

**Tickets.** All three, each card showing the request, who asked, the type,
and a status pill. Selecting one reveals a run bar; running it starts the
agent team through `POST /tickets/{id}/run`.

**Live activity.** The run endpoint is a single blocking POST, so without
help the page would sit still for a minute then jump to the end — hiding
exactly the part worth watching. While a run is in flight the dashboard polls
`GET /events` every 2 seconds, so the timeline fills in as each agent
finishes. The ticket card shows a pulsing ring, an elapsed timer runs, and
agent avatars appear on the card as they participate.

**The timeline** is the audit trail, rendered. Each entry carries the agent's
avatar and colour, what it was asked, what it concluded, the MCP tools it
called, who it delegated to, and — in red — any point where a business rule
refused it. Nothing here is synthesised on the client.

**Status is honest.** A ticket only shows *Resolved* when the backend says
`resolved`. If approvals are pending it shows *Awaiting approval*, which is
the distinction the brief asked for.

**Approvals.** Pending ones first with Approve and Reject buttons wired to
`POST /approvals/{id}`; decided ones below, showing who decided and any note.
The amount, kind, reason, requesting agent and reference are all shown, so a
person can decide without opening the database.

**Cash** sits in the masthead and flashes gold when an approved payment
changes it. When money is committed to open requests it also shows what is
genuinely free.

**Reset** asks for confirmation first, naming exactly what will be cleared
and noting that the original database is never modified.

## One backend gap found and filled

The brief said to identify missing functionality and make only the necessary
change. One thing was genuinely missing: **there was no way to list
approvals.** `POST /approvals/{id}` decided one, and the run response carried
only approvals from that run — so the queue would vanish on a page refresh
and decided ones were invisible.

Added `GET /approvals?status=&ticket_id=`, returning every approval with a
`pending_count`. That is the only backend change this problem required.

## Verification

The preview launcher could not start a dev server from this project path —
it fails with `'C:\Program' is not recognized`, which is a space-in-path
problem in the launcher's own shell, not in the project. Four configurations
were tried (npm, node, an 8.3 short path for node, and a junction at
`C:\hw5-frontend`). The Chrome extension was not connected either, so **no
screenshots were taken**.

What was verified instead, against the real running stack:

| check | result |
| --- | --- |
| TypeScript | `tsc --noEmit` clean |
| Production build | succeeds, 19 modules, 75 kB gzipped JS |
| Dev server | serves the shell with the right title |
| Every module compiles | `main.tsx`, `App.tsx`, `api.ts`, `agents.tsx`, `components.tsx`, `types.ts`, `index.css` all HTTP 200 |
| Vite transform errors | none |
| `GET /api/health` | 200 |
| `GET /api/tickets` | 200, three tickets with real data |
| `GET /api/cash` | 200 |
| `GET /api/approvals` | 200 |
| `GET /api/events` | 200 |
| **Approve button path** | `executed` — balance $3,400 → **$2,560**, exactly $840 |
| **Reject button path** | `rejected` — balance stayed $2,560, nothing moved |
| **Reset button path** | balance back to $3,400, approvals and payments cleared, 3 tickets intact |

The approve/reject/reset rows went through `http://localhost:5173/api/...`,
the same URLs the buttons use, so the proxy and the wiring are both proven.

**Not verified: how it looks.** The layout, animations and responsive
behaviour have not been seen rendered. Everything compiles and every data
path works, but a visual pass is still outstanding.
