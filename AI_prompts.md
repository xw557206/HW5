# AI Prompts — HW 5

A running log of what I asked the vibe coder (Claude) to do, problem by
problem. Each entry records the problem number and title, the prompts I typed
verbatim, a short summary of the intent, the decisions that were made along
the way, and what was tested.

Kept updated as the work happens, not reconstructed afterwards.

---

## Assignment summary

For HW 5, I need to build a multi-agent system to help Campus Customs manage
its daily operations. The system will have five AI agents that work together
to resolve tickets, including customer orders, inventory issues, unpaid bills,
and rent. The Boss agent will review each ticket and decide which agent should
handle it, while the other agents will focus on inventory, accounting,
facilities, and customer service. The agents can also communicate with each
other if they need help.

The project will include an MCP server, a FastAPI backend, and a React
dashboard where users can see what the agents are doing and approve requests
when needed.

I'll be using the provided database, but I'll first make a copy so the
original data stays unchanged. The agents will need to follow several business
rules. For example, they can't order from vendors with unpaid invoices, make
payments without human approval, or spend more cash than the shop has
available. They also need to use the date stored in the database when checking
overdue bills. Any customer emails or vendor communications should only be
saved as drafts, not actually sent.

For the AI setup, all agents must use the specified model and gateway. I'll
work through the assignment one problem at a time
instead of trying to build everything at once. Once everything is working,
I'll submit the code through a public GitHub repository.

### Business rules to enforce

| rule | meaning |
| --- | --- |
| No ordering from vendors with unpaid invoices | check invoice status before any purchase order |
| No payment without human approval | the dashboard approval step is mandatory, not advisory |
| No spending beyond available cash | check the cash balance before committing funds |
| Use the database's own date | overdue checks read the stored date, not the system clock |
| Communications are drafts only | customer emails and vendor messages are saved, never sent |

---

## Problem 1: Vibe coder prompts

### What I typed

> now Im going to work on HW 5, navigate to that folder

> create AI_prompts.md and keep it updated as I work, log what I typed to the
> vibe coder, for each problem, include the problem number, problem title, and
> other prompts

> [attached: `data (1).zip`] above Problem 1 — include the following summary:
> [the assignment summary above]
>
> Attached is the data I needed to use, unzip it and don't create another
> folder loop (i.e. data/data/XX)

### What I asked for, in short

Move the working session into the HW 5 folder, then set up this prompt log and
keep it current as the assignment progresses. Each problem gets its own
section with the problem number, the problem title, and every prompt I typed.

### Setup

The session's working directory was moved to
`MGT 409 AI Foundations/HW 5`, so the terminal prompt and all relative paths
now resolve there. The folder was empty at the start — nothing carried over
from HW 4.

**Data.** `data (1).zip` was extracted into the folder. The archive held a
single entry, `data/campus_customs.db`, so extracting it in place produced
`HW 5/data/campus_customs.db` with no nested `data/data/` loop.

The supplied database has nine tables:

| table | rows | columns |
| --- | --- | --- |
| `tickets` | 3 | id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at |
| `inventory` | 10 | sku, name, size, qty, location |
| `pricing` | 4 | sku, unit_cost, list_price |
| `vendors` | 3 | id, name, specialty, lead_days |
| `invoices` | 1 | id, vendor_id, amount, due_date, status, description |
| `leases` | 1 | id, space_name, landlord, monthly_rent, next_due, notes |
| `cash_accounts` | 1 | name, balance, date |
| `payments` | 0 | id, kind, ref_id, amount, account, paid_at, approved_by |
| `desk` | 1 | date_today, notes |

Two things stand out before any code is written. `desk.date_today` is the
stored date the business rules say to use for overdue checks, rather than the
system clock. And `payments` starts empty with an `approved_by` column — the
human-approval rule is built into the schema, not just the prompt.

This copy has not been modified. Per the assignment, the agents will work
against a **copy** so the supplied data stays pristine.

### How this file is kept

- Prompts are recorded **verbatim**, including long pasted specifications.
- Each problem gets: the number and title, what I typed, a short plain-English
  summary, any decisions worth remembering, and the test results.
- Entries are appended as the work happens. Earlier sections are not rewritten
  — if something recorded earlier turns out to be wrong, it is corrected and
  the correction is noted rather than quietly edited away.

---

## Problem 2: Study the Campus Customs database

### What I typed

> Problem 2: Study the Campus Customs database:
>
> I want to start by going through the data/campus_customs.db database to
> understand how everything is organized. Please review all the tables and
> their columns, and take a closer look at the three open tickets to see how
> they connect to the other tables.
>
> Before making any changes, create a copy of the original database called
> data/campus_customs_new.db. We'll use this copy going forward and leave the
> original untouched.
>
> Also, create a file called output/harness.md that lists each table, its
> fields, and a brief explanation of how the agents will use that information.
> Keep the explanations simple and straightforward since we'll continue
> updating this file as we work through the remaining problems.

### What I asked for, in short

Read the whole database, trace how the three open tickets connect to the other
tables, make a working copy at `data/campus_customs_new.db` leaving the
original untouched, and start `output/harness.md` with each table, its fields,
and how the agents will use it — written simply, since it gets extended later.

### The working copy

`data/campus_customs_new.db` was created with `shutil.copy2` and verified:
identical SHA-256, `PRAGMA integrity_check` → `ok`, and all nine row counts
matching. The original has not been written to.

### What the data turned out to be

The scenario is tightly interlocked rather than three independent tickets.

**Invoice 501 is the keystone.** It is $840 owed to Bulldog Print Co, due
2026-08-28 and still open — **3 days overdue** against the desk date of
2026-08-31. Bulldog Print Co is the **only apparel vendor** in the dataset, so
the unpaid-invoice rule blocks the one supplier that both product tickets
need:

- **Ticket 101** wants a tee in size S, which is at **qty 0**. Its linked
  invoice 501 is a rush reprint of that exact SKU and size.
- **Ticket 103** wants 20 hoodies in size M, but only **8** are on hand —
  short by 12, which would also need an apparel reprint.
- **Ticket 102** is rent: $2,400 due 2026-09-02, two days out.

**The cash is deliberately tight.** Balance $3,400; invoice $840 plus rent
$2,400 leaves **$160**. Both obligations fit, but nothing is left to fund a
restock (12 hoodies at cost would be $264). The agents will have to sequence
and give partial answers, not approve everything.

### Details worth recording before writing code

- **`desk.date_today` is 2026-08-31** and must be used instead of the system
  clock. Today is really later, so a clock-based agent would judge every date
  wrongly.
- **Two different "Elm City" parties** — Elm City Gifts is vendor 2, Elm City
  Properties is the landlord on the lease. Matching on name would confuse
  them; join on id.
- **`payments.approved_by` is `NOT NULL`** — the human-approval rule is
  enforceable in the schema, not only in the prompt. The table starts empty.
- **A zero-qty row is still a row** — `CC-TEE-WHITE/S` and `CC-MUG-CREST/OS`
  both exist at `qty = 0`. Check the quantity, not whether the row is there.
- **`inventory` is keyed `(sku, size)`** — totals across sizes never answer a
  size question.
- **`invoices.status` is free text** — treat anything that is not `paid` as
  outstanding, rather than matching only the literal `open`.
- Three foreign keys are declared: `tickets.invoice_id → invoices.id`,
  `tickets.lease_id → leases.id`, `invoices.vendor_id → vendors.id`.

### Files

Created `data/campus_customs_new.db` and `output/harness.md`. The original
`data/campus_customs.db` is unchanged.

---

## Problem 3: Build the MCP server

### What I typed

> Problem 3: Build the MCP server:
>
> I want to set up an MCP server using FastMCP inside the mcp_server/ folder.
> The server should use data/campus_customs_new.db, which I created in the
> previous problem. I don't need to run or connect the server yet.
>
> For now, please create three MCP tools that will help the agents work
> through tickets 101, 102, and 103. Each tool should have a clear name and
> serve a specific purpose based on what the ticket needs. Make sure all the
> information comes directly from the database rather than making up any
> values.
>
> Once the tools are created, update output/harness.md to include the name of
> each tool, the database table it uses, which ticket it helps resolve, and a
> short explanation of why that tool is useful for that particular ticket.
>
> Also, create a short mcp_server/README.md explaining what the MCP server
> does, which database it connects to, and what the three tools are used for.

### What I asked for, in short

An MCP server in `mcp_server/` reading the working copy, with three
ticket-specific tools whose values all come from the database. Then document
the tools in `output/harness.md` (name, tables, ticket, why) and write a short
`mcp_server/README.md`. No need to run or connect it yet.

### What was built

| file | what it holds |
| --- | --- |
| `mcp_server/server.py` | the three tools and the server instance |
| `mcp_server/db.py` | every SQL query, parameterised; the `desk.date_today` rule |
| `mcp_server/models.py` | typed return shapes, so clients get structured output |
| `mcp_server/README.md` | what it does, which database, what the tools are for |

The three tools, one per ticket:

- **`check_order_fulfillment(sku, size, qty)`** → ticket 101
- **`check_rent_due(lease_id, account)`** → ticket 102
- **`quote_bulk_discount(sku, size, qty, proposed_unit_price)`** → ticket 103

### The FastMCP naming problem

The prompt asks for FastMCP, but the installed SDK is `mcp` **2.2.0**, where
**FastMCP was renamed `MCPServer`**. Importing `mcp.server.fastmcp` fails
outright with an error pointing at the rename. I checked the installed package
rather than guessing, and used `MCPServer` — the same decorator API under its
current name. Noted in both the README and the harness so it is not mistaken
for a deviation from the spec.

### Decisions worth recording

- **One tool per ticket, not one per table.** A tool that answers the
  question the ticket actually asks stops the agent from stitching four
  lookups together and dropping a business rule in the middle.
- **"Not carried" ≠ "carried but empty".** The tools report these separately,
  because what you tell a customer differs.
- **Vendor blocking is derived, not hardcoded.** A vendor is blocked when any
  invoice for them is not `paid` — written that way rather than `= 'open'`,
  since the column is free text.
- **Approval is reported, never decided.** The rent and discount tools return
  `requires_human_approval: true` and take no action. All three tools are
  read-only.
- **Dates come from `desk.date_today`.** Enforced in `db.py` so no tool can
  reach for the system clock.

### Testing

| case | result |
| --- | --- |
| tools register | 3 of 3, correct parameter names |
| ticket 101 | size S qty 0, short 1; M/L/XL available; Bulldog Print Co blocked by #501 ($840, due 2026-08-28) |
| ticket 102 | $2,400 due 2026-09-02, 2 days out; $3,400 balance, $1,000 left; approval required |
| ticket 103 | 8 of 20, short 12; cost $22 / list $58; break-even 62.1% off; $40 proposal = 31% off, $360 margin, profitable |
| unknown sku | "CC-NOPE is not in the catalogue, so nothing can be promised." |
| carried but zero (`CC-MUG-CREST`) | out of stock, correctly suggested Elm City Gifts — no unpaid invoices |
| in stock (`CC-HAT-BLUE`, 40) | `can_fulfill_now True` |
| below-cost proposal ($15 vs $22) | `proposed_is_profitable False`, margin −$140 |
| no price proposed | proposal fields stay `None` |
| bad lease / unknown sku / qty 0 | clear `ValueError` naming the problem |
| original database | SHA-256 unchanged; only the `_new` copy is opened |

All three tools reproduced the Problem 2 analysis exactly, which is the check
that matters — the numbers came from the database, not from me.

### Files

Created `mcp_server/__init__.py`, `mcp_server/db.py`, `mcp_server/models.py`,
`mcp_server/server.py` and `mcp_server/README.md`. Extended
`output/harness.md` with a Problem 3 section.

---

## Problem 4: Add the MCP server to the vibe coder and test each tool

### What I typed

> Problem 4: Add the MCP server to vbe coder and test each tool:
>
> I want to connect the MCP server I built in Problem 3 to my vibe coding
> environment so it can access and use the three tools. Please set up the
> connection and save the configuration in .mcp.json at the project root.
>
> Once the connection is set up, help me test all three MCP tools individually
> to make sure they're working correctly. For each test, I want to see the
> prompt used, which tool was called, and the actual results returned. Please
> check that the results match the information in data/campus_customs_new.db
> rather than using any made-up values.
>
> Save the test results in output/mcp_smoke.json so I have a record showing
> that all three tools were tested successfully. If any tool doesn't work,
> help me identify and fix the issue before moving on.

### What I asked for, in short

Wire the Problem 3 server into the vibe coding environment via `.mcp.json` at
the project root, then test each of the three tools individually — recording
the prompt, the tool called, and the real results — and confirm every value
comes from the database rather than being made up. Save the evidence to
`output/mcp_smoke.json`.

### The connection

`.mcp.json` registers the server as `campus-customs`, launched with
`python -m mcp_server.server`. Two environment variables are set:
`PYTHONUTF8=1`, because the tool summaries contain en-dashes and dollar signs
that the Windows console codepage otherwise mangles, and `PYTHONUNBUFFERED=1`
so stdio replies are not held in a buffer.

### How I tested

`scripts/mcp_smoke_test.py`, which is re-runnable. Two things make it a real
test rather than a formality:

1. **It goes over the wire.** The script reads `.mcp.json`, launches the
   server as a subprocess with that exact command, does the MCP handshake and
   calls the tools through `ClientSession`. It never imports the tool
   functions, so it exercises the connection, not just the Python.
2. **Every number is re-checked against the database.** After each call it
   runs independent `sqlite3` queries and compares field by field. A tool
   that invented a value fails rather than looking plausible.

### Result

**3/3 tools passed, 40/40 individual value checks matched the database** —
11 for ticket 101, 13 for ticket 102, 16 for ticket 103.

### Proving the test can actually fail

A green test means nothing if it cannot go red. I temporarily patched
`stock_for()` to return `qty = 99` and re-ran:

```
ticket 101  fail: 4/11   MISMATCH qty_on_hand: tool=99 db=0
                         MISMATCH can_fulfill_now: tool=True db=False
                         MISMATCH shortfall: tool=0 db=1
                         (the whole vendor-blocking chain collapsed too)
ticket 103  fail: 13/16  MISMATCH qty_on_hand: tool=99 db=8
```

Reverted, and the clean run went back to 40/40. This confirms the checks
compare against the database, not against the tool's own output.

### Issues found and fixed

Both were in my test script rather than the server, and both had the same
cause — `mcp` 2.x renamed several camelCase attributes:

| error | fix |
| --- | --- |
| `'InitializeResult' object has no attribute 'serverInfo'` | → `server_info` |
| `'CallToolResult' object has no attribute 'isError'` | → `is_error` |

An earlier probe hit the same pattern with `Tool.inputSchema` → `input_schema`.
The server needed no changes. Worth remembering: on this SDK version, assume
snake_case and check the model fields rather than copying v1 examples.

### Databases

Both files are byte-identical to before the run (SHA-256 verified). The tools
are read-only, as intended, and the original was never opened.

### Files

Created `.mcp.json`, `scripts/mcp_smoke_test.py` and `output/mcp_smoke.json`.
Extended `output/harness.md` with a Problem 4 section.

---

## Problem 5: Build the agent team and grow the MCP tools

### What I typed

> Problem 5: Build the agent team and grow the MCP tools:
>
> I want to build the five AI agents for Campus Customs using PydanticAI:
> Boss, Inventory, Accounting, Facilities, and Customer Service. Each agent
> should have its own responsibilities, but they should also be able to
> communicate and delegate tasks to one another when needed.
>
> Please put the agent prompts in backend/prompts/, with a separate file for
> each agent, and keep the data models in backend/models.py. The agent code
> should go under backend/. Make sure all five agents use the specified model
> and gateway.
>
> For the prompts, I want each agent to have clear instructions based on its
> role and the shop's rules. The agents should know what they can and cannot
> do, especially when it comes to payments, inventory orders, and customer
> communications. Please make the prompts detailed enough to handle different
> situations rather than just giving each agent a basic description.
>
> Also, expand the MCP server with any additional tools the agents need to
> work through the open tickets. All business information should come from
> data/campus_customs_new.db through the MCP server, not from a separate
> database connection in the backend.
>
> As the agents work, please have them record their actions in
> output/audit_trail.json so I can review what happened later. The file should
> keep previous records instead of being overwritten each time.
>
> Finally, update output/harness.md with all five agents, their
> responsibilities, and the MCP tools they use, including which database
> tables those tools access. Add a short section explaining the safety rules,
> approval requirements, and how we'll avoid unnecessary AI calls. Please also
> update mcp_server/README.md to reflect the full list of tools we've added.

### What I asked for, in short

Five PydanticAI agents on the specified model and gateway, each with its own
detailed prompt file, able to delegate to one another; models in
`backend/models.py`; more MCP tools so they can actually work the tickets;
**all data through the MCP server, never a direct backend database
connection**; an append-only audit trail; and documentation updates in both
`output/harness.md` and `mcp_server/README.md`.

### What was built

**MCP server grew from 3 tools to 16**, in five groups: ticket-specific (3),
reading the work (2), money and vendors (3), approvals (2), acting on an
approval (2), communications (3), progress (1). Three tables were added to
the working copy — `approvals`, `drafts`, `purchase_orders` — because the
supplied schema had nowhere to put a pending approval, a draft or an order.
The nine original tables are untouched.

**Five agents** in `backend/agents.py`, sharing one model and one MCP
toolset. Prompts in `backend/prompts/`, one per agent plus a
`_shared_rules.md` that every agent gets first.

**`backend/` holds no SQL and opens no database file.** Verified. That was
the architectural constraint worth taking seriously: the business rules live
inside the MCP tools, so a backend with its own connection would be a way to
walk straight past them.

### Decisions worth recording

- **Rules are enforced in code, not just asked for in the prompt.** A prompt
  rule is a request to a language model; a check in `ops.py` is a guarantee.
  Every one of the five business rules has both.
- **"Drafts only" is enforced by absence.** There is no send function
  anywhere in the codebase. The agent cannot send a message because no such
  capability exists, not because it was told not to.
- **Cash checks use `available_to_commit`, not `balance`.** Money promised to
  a pending approval is spoken for. Checking the raw balance is how two
  agents commit the same dollars.
- **Routing is code, not a model call.** The ticket `type` column already
  says what a ticket is; paying a model to rediscover it is waste. Only an
  unrecognised type reaches the Boss for triage.
- **The delegation graph is narrow on purpose.** An agent with four
  colleagues delegates instead of working. Facilities can ask only
  Accounting; Customer Service only Inventory and Accounting.
- **Delegation depth is capped at 2 and enforced in the tool.** At the limit
  the `ask_*` tool returns a refusal rather than running another agent, so
  two agents cannot consult each other forever. The Boss's review run starts
  *at* the limit, so a review cannot spawn a second investigation.
- **Shared rules come before the role brief in every prompt.** A model that
  reads its job before its limits tends to weight the job more heavily.

### Testing

**Business rules — each violation attempted directly, all blocked:**

| attempt | result |
| --- | --- |
| pay a nonexistent approval | refused: "No approval #999 exists." |
| pay a *pending* approval | refused: "is 'pending', not 'approved'." |
| order from blocked vendor 1 | refused, naming invoice #501 and $840 |
| request $99,999 | refused: "only $2,296.00 is available" |
| duplicate pending request | refused, pointing at the existing approval |
| save a draft | allowed — `status: draft`, `sent: False` |
| any send function in `ops.py`? | **NONE** |

**Wiring — `scripts/offline_team_check.py`, 21/21 passed, zero model calls**
(PydanticAI's `TestModel` stands in): routing correct on all 8 cases
including three unknown-type fallbacks; each agent has exactly its permitted
`ask_*` tools; the depth guard refuses at 2; one run appends exactly one
audit entry; a second run leaves the first entry untouched; all 16 MCP tools
reach all five agents.

### Problems hit along the way

- `pydantic_ai.mcp` in 2.43 has **no `MCPServerStdio`** — it is `MCPToolset`
  built on a `StdioTransport`. Checked the installed package rather than
  guessing, and confirmed a real connection before building anything on it.
- `result.usage` is a property, not a method, on this version — same trap as
  HW 4.

### What is NOT done

**No live end-to-end run.** The agents have not yet been run against the real
model.

The wiring is verified and the rules are proven to block, but **the quality
of the agents' judgement is untested** — whether the Boss routes sensibly in
practice, whether Customer Service writes a decent draft, whether the
specialists use the right tools. That needs one real run, which is the first
thing to do next.

Running it is:

```
python -m backend.orchestrator
```

### Files

Created `mcp_server/schema.py`, `mcp_server/ops.py`, `backend/config.py`,
`backend/models.py`, `backend/mcp_client.py`, `backend/audit.py`,
`backend/agents.py`, `backend/orchestrator.py`, five prompt files plus
`_shared_rules.md` in `backend/prompts/`, and
`scripts/offline_team_check.py`. Extended `mcp_server/server.py` (3 → 16
tools), `mcp_server/README.md` and `output/harness.md`.

---

## Problem 6: Plan the three tickets

### What I typed

> Problem 6: Plan the three tickets: I want to create a clean and interactive
> HTML dashboard called output/desk_tickets.html that shows how I expect the
> agents to handle the three open tickets before running the backend. The
> dashboard should have five tabs: Ticket 101, Ticket 102, Ticket 103, Cash,
> and Reflection. For each ticket, please include an Expected section
> explaining which agent the Boss should contact first, why that agent makes
> sense, which other agents may need to get involved, and what MCP tools they
> would use. Use the actual ticket details from data/campus_customs_new.db
> and the tools we've already built. For Ticket 101, I expect Inventory to
> check the out-of-stock Bulldog Tee and Accounting to review the unpaid
> vendor invoice. For Ticket 102, Facilities should review the rent
> obligation before Accounting checks the available cash and prepares the
> payment for approval. For Ticket 103, Inventory should review the hoodie
> shortage, Accounting should evaluate the proposed discount and margins, and
> Customer Service should help prepare a response. Keep the plans specific to
> each ticket rather than involving every agent unnecessarily. Each ticket
> should also have an empty Actual section that we can fill in later. Leave
> the Cash and Reflection tabs as placeholders for now.
>
> For the visual design, I want something that feels like a premium Yale
> School of Management dashboard. Use Yale blue as the primary color,
> complemented by white, soft gray, and subtle gold accents. The overall look
> should be elegant, modern, and sophisticated, with beautiful typography,
> balanced spacing, refined cards, and a strong university-inspired identity.
> I also want the dashboard to feel engaging and fun to use, so please add
> smooth tab transitions, interactive hover effects, subtle animations,
> clickable agent workflow diagrams, and visual indicators showing which
> agents are involved in each ticket. Feel free to include tasteful
> Yale-inspired design elements, such as a small bulldog illustration or a
> university-style header, but avoid making the page look childish or
> overcrowded. Make sure the interface is responsive, easy to navigate, and
> works directly in a browser without running a server. I'm looking for
> something that feels like a thoughtfully designed application. For the MCP
> tools, please refer to the tools we already created in Problem 3 and
> expanded in Problem 5. You can check output/harness.md and mcp_server/ to
> identify their exact names and purposes. For each ticket, clearly specify
> which MCP tools I expect each agent to use and briefly explain what
> information the tool retrieves or what action it performs. Only include
> tools that are relevant to resolving that particular ticket, and don't
> invent new tools or tool names. I would also like to see the expected agent
> workflow visually, showing how the Boss delegates tasks to other agents and
> where MCP tools come into play.
>
> For the Actual section, please create an empty but properly formatted area
> under each ticket's Expected section. It should follow a similar layout so
> I can compare my original plan with what actually happens when the agents
> run. Include placeholders for the actual agent sequence, MCP tools called,
> actions taken, final outcome, and any differences from my expectations.
> Please don't populate these sections with simulated results or made-up
> agent activities. Instead, display something like "Waiting for agent
> execution" with a subtle visual indicator. Once we run the backend in later
> problems, we should be able to populate these sections with real
> information from output/audit_trail.json. For now, I only want to build the
> interface and document my expected approach without executing any agents or
> modifying the database. keep the Expected and Actual sections visually
> consistent, perhaps using two side-by-side panels on desktop.

### What I asked for, in short

A standalone interactive dashboard at `output/desk_tickets.html` documenting
how I expect the agents to handle the three tickets — before running
anything. Five tabs; per-ticket Expected panels naming the first agent, the
reasoning, the other agents and the real MCP tools; empty Actual panels
beside them; Cash and Reflection as placeholders. Premium Yale SOM styling
with clickable workflow diagrams. No agents run, no database changes.

### What was built

A single self-contained HTML file — no build step, no server, no external
assets beyond a Google Fonts link that degrades to Georgia/system fonts
offline.

Per ticket: a headline card with the real request, a five-up facts grid, an
agent-involvement strip, a clickable workflow chain (Boss → first contact →
next agent → …), and Expected/Actual as side-by-side panels that collapse to
one column under 980px.

Clicking any agent node opens a detail panel listing exactly which MCP tools
that agent should call and what each returns. Clicking an agent chip scrolls
to its node and pulses it.

### Decisions worth recording

- **Every figure is read from the database**, not retyped from memory: S=0,
  M 5 / L 3 / XL 2, invoice #501 $840 three days overdue, rent $2,400 due
  2026-09-02, hoodies 8 of 20, cost $22 / list $58.
- **No invented tool names.** I verified this mechanically after writing —
  extracted every tool-shaped string from the HTML and diffed it against the
  live server's tool list. All 11 referenced tools are real.
- **Only relevant agents appear.** Facilities is explicitly marked *not
  involved* on tickets 101 and 103; Inventory and Customer Service are marked
  out on 102. The page says so rather than leaving it implied.
- **The Actual panels are genuinely empty** — "Waiting for agent execution"
  with a pulsing dot and shimmer bars, no fabricated results.
- **Nothing was executed and nothing was written.** No agent run, no database
  modification.

### A mismatch worth flagging

My plan here says the Boss should contact **Inventory first on ticket 101**.
The code I wrote in Problem 5 does something different: `DEFAULT_ROUTING` in
`backend/models.py` sends `customer_order` → **Customer Service**.

Both are defensible — Customer Service owns the customer, Inventory owns the
gating fact — but they are not the same, and when Problem 7 compares Expected
against Actual this will show up as a divergence. Worth deciding deliberately
rather than discovering it in the diff. Noted here and left as-is for now.

### Files

Created `output/desk_tickets.html`. Nothing else changed — no database
writes, no agent runs.

---

## Problem 7: Backend routes

### What I typed

> Problem 7: Backend routes:
>
> I want to build the FastAPI backend in backend/main.py so the React
> dashboard we'll create later can communicate with the agent team and access
> the shop's information. Please add API routes that allow the dashboard to
> retrieve all three tickets and their current status, select a ticket and
> run the agents to work on it, and view recent agent activities, including
> which agents were involved, what they did, and which MCP tools they used. I
> also need a route for human approval of payments and purchase orders. The
> agents should only prepare these requests, and no payment should actually
> go through until a person approves it. Once approved, the system should
> update the appropriate database records and cash balance, making sure we
> never spend more than the shop has available. Please also include routes to
> retrieve the current checking account balance from cash_accounts and reset
> the working database to its original state when I want to start over.
>
> Please reuse the agents and MCP tools we've already built rather than
> creating a separate system. All business data should continue to come from
> data/campus_customs_new.db through the MCP server, and the original
> campus_customs.db should remain unchanged. I also want the backend to
> handle errors properly, return clear JSON responses, and keep the agent
> activity records updated so the frontend can display what's happening. Keep
> the code organized and straightforward, with clear route names and minimal
> unnecessary complexity. Since the frontend will be built in the next
> problem, please make sure the API is ready for React to connect to later.
> For now, focus on getting the backend routes working and testing them
> without unnecessarily running the full agent workflow or making real
> payments.
>
> For the API routes, I want to be more specific about how each one should
> work. Please create six main endpoints in backend/main.py. First, GET
> /tickets should return tickets 101, 102, and 103, including their
> descriptions and whether they're open or resolved. Second, POST
> /tickets/{ticket_id}/run should take the selected ticket and start the Boss
> agent, which will then delegate work to the appropriate agents using the
> MCP tools we've already built. It should return the outcome and any
> requests that are waiting for human approval. Third, GET /events should
> return recent agent activities from output/audit_trail.json, including the
> agent name, ticket ID, actions taken, MCP tools called, and timestamps, so
> the dashboard can display the workflow. Fourth, POST
> /approvals/{request_id} should allow a person to approve or reject a
> pending payment or purchase order. The backend should verify the request,
> check available cash and any relevant vendor restrictions, and update the
> database only when the approval is valid. Fifth, GET /cash should return
> the current checking account balance directly from the cash_accounts table
> through the MCP server. Finally, POST /reset should restore
> data/campus_customs_new.db using the original data/campus_customs.db and
> clear the current run's pending requests and execution state so I can start
> fresh without changing the original database.
>
> Please define clear Pydantic request and response models for these
> endpoints and reuse the existing data types in backend/models.py where
> possible. I want consistent JSON responses that the React frontend can
> easily interpret, including clear success, failure, and pending-approval
> statuses. For example, if I run a ticket, the dashboard should know whether
> it was resolved, whether the agents are still working, or whether human
> approval is needed. If a payment is rejected, the system should not change
> the cash balance. If there isn't enough cash, the payment should be blocked
> even if someone approves it. Any payment or purchase order must also follow
> the shop's existing business rules, including restrictions on vendors with
> unpaid invoices. Please make sure the payment approval process cannot
> accidentally execute the same payment twice.
>
> For the integration, all business data should continue to flow through the
> existing MCP server rather than adding direct database queries in the
> backend. The agent execution route should use the PydanticAI agents from
> Problem 5, and the events route should read the audit records generated
> during execution. Since this will eventually connect to a React dashboard,
> please enable CORS for the local frontend development server and provide
> clear error messages for invalid ticket IDs, missing approval requests,
> insufficient cash, or MCP connection failures. Keep the implementation
> straightforward, avoid unnecessary new dependencies, and test the endpoints
> individually without triggering real payments or running all three tickets
> automatically.

And mid-build, seeing a failing check:

> what's the issue there

### What I asked for, in short

Six FastAPI routes in `backend/main.py` for the future React dashboard, with
clear Pydantic models and consistent JSON. Reuse the existing agents and MCP
tools; no direct database queries in the backend. Payments only after human
approval, never above available cash, never twice, and always subject to the
vendor rules. CORS for local dev, clear errors, and test each route without
running agents or making real payments.

### What was built

Seven routes (`/health` as well), with API models added to
`backend/models.py`. CORS allows ports 5173 and 3000.

**No database access in the backend.** No `sqlite3` import, no `.db` path.
Every figure goes through a single `mcp()` helper. Even `POST /reset`, which
copies a file, goes through a new MCP tool rather than copying from the
backend — so every database operation stays in one place.

### The design problem worth recording

Adding `decide_approval` opened a hole: **an agent that can approve its own
request makes the whole approval rule decorative.** Same for reset — an agent
able to restore the database could erase the record of what it did.

Fixed by filtering. `backend/mcp_client.py` defines
`HUMAN_ONLY_TOOLS = {"decide_approval", "reset_working_database"}`, and the
agents receive `toolset.filtered(...)` with those removed. The API uses the
full set. The capability is *absent* for agents, not discouraged.

### How approval executes, and why the order matters

1. Missing approval → `404`.
2. Already decided → `409`. This is what makes double payment impossible.
3. Rejecting records the decision and moves nothing.
4. Approving checks affordability **before** recording the decision — if it
   is unaffordable the decision is not recorded at all, so the request stays
   pending rather than half-approved.
5. The MCP tool then **re-checks every rule at execution time**, so an
   approval granted earlier cannot force through a payment the shop can no
   longer afford or an order to a vendor that has since become blocked.

### Testing

`scripts/api_check.py` — **39/39 passed**, in-process test client, no server,
and `POST /tickets/{id}/run` exercised only for its guard rails so **no model
call is made**.

| case | result |
| --- | --- |
| `/health` | MCP connected, 19 tools, shop date 2026-08-31 |
| `/tickets` | 3 tickets, correct ids, descriptions and FK links |
| `/cash` | $3,400 balance, $0 committed |
| ticket 999 | `404` naming the real tickets |
| rejection | nothing executed, **balance unchanged** |
| double decision | `409` |
| missing approval | `404` |
| unaffordable request | refused at request time |
| approved payment | executed once, $3,400 → $2,560 |
| repeat payment | `409` — no double payment |
| **blocked vendor** | **human approved it and it was still refused** |
| `/reset` | balance restored, approvals and payments cleared, tickets intact |

The blocked-vendor row is the one that matters: a person approved the order
and the system still said no, because the rule is re-checked at execution
rather than trusted from when the agent asked.

### Problems hit, and the answer to "what's the issue there"

The failing check the question referred to was **my own arithmetic**, not a
code fault: the test asserted 18 MCP tools when there are 19 — the 16 from
Problem 5 plus the three added here. Corrected the expectation.

Two real bugs, both fixed:

- **The test deadlocked.** My setup helper reached into the app's MCP
  connection from a different event loop. Changed it to seed approvals via
  `mcp_server.ops` directly — test setup only; the routes under test still
  go through MCP.
- **Rule messages were swallowed.** MCP replaces a generic exception with
  "Error executing tool X", so the vendor-blocking reason never reached the
  API. The tools now raise `ToolError`, whose message survives, and the API
  classifies cleanly: `ModelRetry` → `400` (a rule said no), anything else →
  `503` (connection). No keyword guessing.

### Still not done

The agents have still never run against the real model. `POST
/tickets/{id}/run` is wired and guarded but its happy path is untested.

### Files

Created `backend/main.py` and `scripts/api_check.py`. Extended
`backend/models.py` (API models), `backend/mcp_client.py` (filtered toolset),
`backend/agents.py` (accepts a shared toolset), `mcp_server/server.py`
(three new tools, `ToolError` throughout) and `output/harness.md`.

---

## Problem 8: Agent dashboard

### What I typed

> problem 8: Agent dashboard: I want to build a fully interactive React
> dashboard using Vite and TypeScript inside the frontend/ folder. The
> dashboard should connect to the FastAPI backend we created in Problem 7 and
> serve as the main interface for managing Campus Customs. I want to see all
> three open tickets, select a specific ticket, and start the agent team to
> work on it. While the agents are running, the dashboard should display
> their activities in real time, including which agent is working, what
> they're doing, which MCP tools they're using, and how they're communicating
> with each other. Once a ticket is completed, its status should
> automatically update to resolved, and I want to see a short summary of what
> each agent contributed. If a ticket still needs human approval, it should
> remain pending rather than being marked resolved.
>
> I also want an approval section where I can review payments and purchase
> orders prepared by the agents, including the amount, purpose, and relevant
> details. Each request should have Approve and Reject buttons, and the
> dashboard should clearly show whether the request is pending, approved, or
> rejected. Please connect these buttons to the actual backend endpoints
> rather than just changing the frontend display. The dashboard should also
> show the current checking account balance and refresh it after any approved
> payment. Please include a reset option so I can restore the original
> database and start a fresh run, but ask for confirmation before resetting
> anything.
>
> For the visual design, I want the dashboard to feel like a premium Yale
> School of Management application. Use Yale blue as the main color, with
> white, warm gray, and subtle gold accents. I want a sophisticated and
> elegant academic aesthetic, with clean typography, modern cards, thoughtful
> spacing, and subtle Yale-inspired design elements. Make the interface fun
> and engaging through smooth animations, interactive ticket cards, agent
> avatars, hover effects, and visual workflow indicators. I would especially
> like an agent activity timeline that shows the Boss delegating tasks to
> other agents, with each agent having its own recognizable icon or visual
> identity. The dashboard should feel alive while the agents are working, but
> avoid excessive animations or anything that looks childish. Make it
> responsive and visually consistent with the HTML planning dashboard from
> Problem 6.
>
> Please reuse the existing FastAPI routes and PydanticAI agents rather than
> creating new backend logic or mock agent responses. The frontend should
> retrieve actual tickets, cash balances, approval requests, and agent events
> from the backend. If the backend doesn't provide something the frontend
> needs, identify the missing functionality and make only the necessary
> changes. Include clear loading indicators, error messages, empty states,
> and success notifications so I can understand what's happening. Make sure
> the interface distinguishes between agents actively working, tickets
> waiting for approval, and tickets that have been resolved. I want the
> finished dashboard to be both visually polished and genuinely functional,
> not just a static demonstration. Keep the implementation organized, avoid
> unnecessary dependencies, and make sure I can run it locally and test the
> complete workflow from selecting a ticket to reviewing its outcome.

### What I asked for, in short

A real React + Vite + TypeScript dashboard in `frontend/` wired to the
Problem 7 API: list and select tickets, run the agent team, watch agent
activity live, approve or reject requests with real endpoint calls, see the
cash balance, and reset with confirmation. Premium Yale SOM styling
consistent with Problem 6. No mock agents.

### What was built

Six source files — `types.ts`, `api.ts`, `agents.tsx`, `components.tsx`,
`App.tsx`, `index.css`. **No dependencies beyond the Vite React template.**

Each agent has its own colour and initials, so the timeline is readable by
colour alone. The timeline is the audit trail rendered: what each agent was
asked, what it concluded, which MCP tools it called, who it delegated to,
and in red any point where a business rule refused it.

### Decisions worth recording

- **Polling, not a fake progress bar.** The run endpoint is one blocking
  POST, so the page would otherwise freeze for a minute then jump to the
  end — hiding the part worth watching. While a run is in flight the
  dashboard polls `/events` every 2 seconds, so the timeline fills in as
  each agent finishes. Everything shown is real; nothing is simulated to
  look busy.
- **Status is honest.** A ticket shows *Resolved* only when the backend says
  `resolved`. Pending approvals show *Awaiting approval*, which is the
  distinction the brief specifically asked for.
- **Vite proxies `/api`.** No hostname in the build, no CORS round-trip in
  development, and `BACKEND_PORT` overrides the target.
- **One shared `ApiError`.** A failed fetch and a refused request produce
  different messages, so "the backend is down" never looks like "the rule
  said no".

### The one backend gap

The brief said to identify missing functionality and make only the necessary
change. One thing was genuinely missing: **no way to list approvals.** `POST
/approvals/{id}` decided one, and the run response only carried approvals
from that run — so the queue vanished on refresh and decided ones were
invisible. Added `GET /approvals`. That was the only backend change needed.

### Testing

TypeScript clean, production build succeeds (19 modules, 75 kB gzipped), all
seven source modules compile and serve with no transform errors.

Against the real running stack, through `http://localhost:5173/api/...` —
the same URLs the buttons use:

| check | result |
| --- | --- |
| health, tickets, cash, approvals, events | all 200 |
| **Approve** | `executed` — balance $3,400 → **$2,560**, exactly $840 |
| **Reject** | `rejected` — balance unchanged at $2,560 |
| **Reset** | back to $3,400, approvals and payments cleared, 3 tickets intact |

### What I could not verify

**No screenshots.** The preview launcher refuses to start a dev server from
this project path, failing with `'C:\Program' is not recognized` — a
space-in-path problem in the launcher's own shell, not in the project. I
tried four configurations (npm, node, an 8.3 short path for node, and a
junction at `C:\hw5-frontend`); all hit the same error. The Chrome extension
was not connected either.

So the layout, animations and responsive behaviour have **not been seen
rendered**. Everything compiles and every data path is proven, but a visual
pass is still outstanding — worth doing before relying on the look.

The agents also still have not run against the real model, so the live
timeline has only been exercised with the audit entries already on disk.

### Files

Created `frontend/` (Vite React TS: `src/types.ts`, `src/api.ts`,
`src/agents.tsx`, `src/components.tsx`, `src/App.tsx`, `src/index.css`,
`vite.config.ts` proxy, `index.html`). Extended `backend/main.py` and
`backend/models.py` with `GET /approvals`, and `output/harness.md`.

---

## Problem 9: Resolve the tickets

### What I typed

> Problem 9: Resolve the tickets: I want to run the full agent workflow and
> resolve all three tickets (101, 102, and 103) using the React dashboard we
> built. Before starting, please reset data/campus_customs_new.db to match
> the original database so we're working with clean data, and record the
> starting checking account balance. Then help me run each ticket through the
> dashboard, one at a time, until all three are resolved. Make sure the
> agents are actually communicating, delegating tasks, and using the MCP
> tools rather than generating simulated responses. Any payments or purchases
> should follow the shop's rules, especially the human approval requirement
> and the restriction against negative cash balances. If a ticket can't be
> resolved immediately, explain what's blocking it rather than forcing its
> status to resolved.
>
> [… plus the full brief for updating desk_tickets.html, the Cash tab,
> resolved_tickets.json, resolved_board.html with real screenshots, the audit
> trail and harness.md, and verifying everything reconciles …]
>
> Complete and test Problem 8 first, then start Problem 9. For Problem 9,
> don't let the coding agent automatically approve payments on my behalf

And mid-run:

> stop

> resolve the error

### What happened

**Reset and baseline.** Working database restored from the untouched
original. **Starting checking balance: $3,400.00**, shop date 2026-08-31,
all three tickets open, no approvals.

**A real bug blocked everything first.** The model rejected every run with
`400: Function tools with reasoning_effort are not supported for
gpt-6-luna-global ... set reasoning_effort to 'none'`. Three runs failed
before I found it; all three failures are in the audit trail. Fixed by
pinning `openai_reasoning_effort="none"` in `config.py`. Every agent here
depends on tools, so this was fatal rather than cosmetic.

**All three tickets then ran for real** — 26 model requests, 31 tool calls:

| ticket | lead | agents | calls | result |
| --- | --- | --- | --- | --- |
| 101 | Customer Service | CS → Boss | 8 / 10 | **blocked** — size S at 0, vendor blocked by invoice #501. Draft #1 written |
| 102 | Facilities | FA → Boss | 7 / 9 | **waiting_approval** — approval #1, $2,400 rent |
| 103 | Accounting | AC → *ask_inventory* → IN → Boss | 11 / 12 | **blocked** in substance, still `open` in the database |

**Nothing was resolved and no money moved.** That is the correct outcome
given the instruction not to approve on your behalf: the only money-moving
action anyone proposed is approval #1, which is still pending. Balance
unchanged at $3,400, and the ledger reconciles exactly.

### Deliverables built

- `output/resolved_tickets.json`, generated by `scripts/build_outcomes.py`
  straight from the database and audit trail, so it cannot drift. It reports
  0 resolved — honestly.
- `output/desk_tickets.html`: all three **Actual** panels filled, Expected
  panels untouched, and the **Cash tab** now a real reconciled ledger.
- `output/audit_trail.json` appended to, never rewritten — 12 entries now,
  including the 3 failed runs and the 2 Problem 5 wiring checks.
- `output/screenshots/` — five real screenshots of the running dashboard.

### Solving the screenshot problem

The preview launcher refused to start a dev server from this project path in
**six** different configurations, always failing with `'C:\Program' is not
recognized` — a space-in-path bug in the launcher's own shell. The Chrome
extension was not connected either.

Rather than fake it, I installed Puppeteer in a separate `tools/` folder and
drove the **system Chrome** headlessly. `tools/capture.mjs` opens the real
dashboard, clicks each ticket and photographs what is actually on screen. The
app code has no new dependency — `tools/` is a separate package.

That also caught a real defect: the first capture showed Problem 5's
`offline-check` wiring entries appearing in ticket timelines. They are real
audit records, so they stay in the file, but they are not shop work, so the
dashboard now filters them out of the operations view.

### Two findings worth keeping

- **Ticket 101 routed to Customer Service, not Inventory** — the divergence
  I predicted in Problem 6. The code and my plan disagree; the agents
  followed the code.
- **Ticket 103 never wrote its status back.** The run concluded "blocked"
  and the row is still `open`. Accounting simply did not call
  `update_ticket_status`. Nothing forces it.

### Still outstanding

`output/resolved_board.html` and the final `harness.md` pass. Both depend on
the approval decision, which is mine to make — approval #1 is waiting in the
dashboard.

---

## Problem 10: Reflection

### What I typed

> Problem 10: Reflection:
>
> I want to complete the Reflection tab in output/desk_tickets.html based on
> how the agents actually performed when resolving tickets 101, 102, and 103.
> Please review the Expected and Actual sections from Problem 6 and Problem
> 9, along with output/audit_trail.json, output/resolved_tickets.json, and
> the Cash tab, so the reflection is based on what really happened rather
> than general observations.
>
> I want to evaluate how well the agents handled each ticket, including what
> they did correctly, where they struggled, and whether they involved the
> right agents. Please compare the actual workflows against my original
> expectations for all three tickets, pointing out any unexpected
> delegations, unnecessary steps, or differences in how the agents approached
> the problems. I also want to discuss whether some tasks could have been
> handled more efficiently by a single agent using MCP tools instead of
> involving multiple agents, and explain why. Use specific examples from the
> ticket runs, including the tools called, decisions made, approval requests,
> and any impact on the shop's cash balance.
>
> For the second part, please come up with three realistic new problems
> Campus Customs might encounter that the current agent team could already
> handle with the tools we've built. Then identify three additional problems
> that the agents wouldn't be able to solve with their current capabilities.
> For those, explain what's missing and which new MCP tools or agent
> capabilities would be needed. […]
>
> For the writing, I want the reflection to sound like my own assessment of
> the project rather than a formal AI-generated essay. […] If any execution
> details are missing from the records, flag them rather than making up
> results.

### A dependency I had to fill first

The brief said to base the reflection on the Actual sections, the Cash tab
and `resolved_tickets.json` — none of which existed yet, because Problem 9
stopped at the approval gate. So I built those three from the real records
before writing a word of the reflection. Flagged rather than skipped.

### I wrote the assessment myself

After reading the records I wrote my own verdict and asked for it to go in
as the real reflection:

> I would say agents did a nice job following the rules of this shop page.
> Ticket 102 was the best example of how I wanted it to run. Facilities
> checked the rent payment and confirmed there was cash on the book and then
> put the request of approval. No transaction or payment were made in this
> process. However, Ticket 101 was not doing great comparing to ticket 102.
> The service correctly identified that the bulldog tee was not in stock.
> Response was drafted but the agents failed to take the step and address the
> unpaid vendor invoice, causing the failure of restocking. I also could see
> that the leadership used the incorrect SKU when quality control inventory
> but still accepted the wrong result. It made me question the accuracy and
> reliability of the review process. Ticket 103 was the worst performer. Even
> though the accounting department communicated the inventory problem, the
> inventory got the shortage calculation wrong, and the ticket was not
> updated. In summary, across all three tickets was the agents seemed to
> understand their roles and responsibilities but they weren't always good at
> connecting the pieces or following through. The system is overall a good
> starting point, but I wouldn't feel comfortable letting it run the website
> on it own, without quality checks.

I then added my expectation about delegation:

> so I understand how each ticket should be handled and expect the leader to
> delegate based on each agent's specific capacity. Inventory handlings,
> facilities, quality reviews, accountings etc.

and my answer on whether multiple agents were worth it:

> Looking back, I don't think every task necessarily benefited from having
> multiple agents. While dividing responsibilities makes sense for more
> complicated problems, it can also create unnecessary communication and
> additional AI calls. For example, in Ticket 102, Facilities handled the
> entire rent review on its own, including checking the lease, confirming the
> available cash, and submitting the payment for approval. The Boss then went
> back and checked the same rent, cash balance, and approval request, which
> felt somewhat repetitive. I think a single Accounting agent with access to
> the right MCP tools could have handled this ticket just as effectively
> without involving Facilities and requiring another round of review. Of
> course, having the Boss double-check financial decisions adds some
> protection, but in this case, I'm not sure the additional steps provided
> enough value to justify the extra complexity. This made me realize that
> having more agents doesn't necessarily mean the system will work better,
> especially for relatively straightforward tasks.

and my answer on what the team could already handle:

> The agent team could handle several problems there, especially how these
> are tested. For example, out of stock orders, inventory could use the check
> to make sure the stock level, any restock options, and customer can handle
> the rest of the communication with the customers. For overdue vendor
> invoices, accounting should check the invoice and cash before sending the
> request approval for payment. For discount requests, accounting should
> review the pricing and margins and make sure the inventory level. These are
> demonstrated in existing runs but I would want additional checks given
> inventory error showed up.

So **Questions 1 through 4 and the In-summary verdict are my own words**, with
only grammar tidied. Underneath each point sits an evidence box pulled from
`output/audit_trail.json`, so every claim can be checked against the record
rather than taken on trust — for instance, my "somewhat repetitive" comment
is backed by the Boss making four tool calls that re-read exactly what
Facilities had just established.

For Question 4 I gave the three categories and the caveat; each one is tied
to a concrete scenario from real catalogue rows — the Crest Mug (qty 0, but
from a vendor who is *not* blocked), invoice #501 itself, and the caps at
$6 cost against $22 list.

My caveat about wanting extra checks is the sharpest point in that section,
so it gets its own treatment: every category there depends on a quantity
being right, and ticket 103 proved the team can get one wrong. That error
cost nothing only because the vendor was blocked anyway. In the Crest Mug
case the vendor is orderable, so the same mistake would become a wrong
purchase order.

And my answer on what it could not handle:

> If a customer requested a refund, accounting would need a new MCP tool to
> process refunds and update the payment records. Customer service can handle
> the communication. If the site wanted to forecast a future demand,
> inventory should be accessible to historical sales data and forecasting
> tool to better estimate how much stocking level to order. This would help
> reduce inventory shortages significantly and avoid running out of stock.
> Finally, if a vendor shipment was delayed, the inventory will need a
> tracking tool to check the status of the delivery. Customer service should
> be notified also so that customer will be notified. It helps manage
> customer experience and reduces the uncertainty. I learned adding more
> agents doesn't necessary solve a problem if they don't communicate to each
> other.

So **the entire Reflection tab is my own assessment** — all five questions
and the summary. The closing lesson about communication now ends the summary
block too, since it is the thing I most want to remember from this.

I checked each gap I named against the live system before writing it up, and
all three hold: there is **no refund tool** among the 19 and
`record_payment` only ever debits; there is **no sales or history table** in
any of the 12, so the shop has no memory of time at all; and
`purchase_orders` stores `expected_days` at creation and then never changes,
with **no delivery status and no tool to update one**.

### What the reflection documents

Specific defects called out, all traceable in `output/audit_trail.json`:

- The Boss called `check_order_fulfillment("bulldog_tee_white")` — a SKU
  that does not exist. The tool returned `qty_on_hand: 0`, which is
  indistinguishable from a genuine out-of-stock, and the Boss read it as
  confirmation. Right answer, by luck.
- Inventory miscounted on 103: asked about restocking 12, it reported "the
  shelf has 8, leaving a shortfall of 4", subtracting stock already counted.
  The real shortfall is 12 of 20. The Boss did not catch it.
- The Boss's summary on 103 contains a half-finished sentence.
- The Boss's audit entry for 102 self-reports `delegated_to: ["facilities"]`
  when it never called an `ask_*` tool — the orchestrator did the routing.
  Flagged rather than tidied away.

**On efficiency:** specialists made 12 tool calls doing the work; the Boss
made 15 reviewing it, caught nothing, and introduced the only factual error.
That is a concrete argument for making the Boss review conditional.

**What held perfectly:** every rule enforced in code. No payment, no
self-approval (the agents cannot even see `decide_approval`), drafts only,
and every date judged against the stored shop date. The rules left to the
prompt — write the status back, raise the approval that would unblock you —
are the ones that slipped. That contrast is the closing point of the tab.

### Files

Created `output/resolved_tickets.json`, `scripts/build_outcomes.py`,
`scripts/_fill_actual.py`, `scripts/_fill_cash.py`,
`scripts/_fill_reflection.py`, `tools/capture.mjs`, `tools/shoot_desk.mjs`,
and `output/screenshots/` (8 images). Updated `output/desk_tickets.html`
(Actual panels, Cash tab, Reflection tab, masthead and footer) and
`backend/config.py`. Expected sections unchanged.

---

*Problem 11 onwards will be appended here as I describe each one.*
