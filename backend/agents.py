"""The five Campus Customs agents.

All five share one model (gpt-6-luna through Portkey) and one MCP toolset, so
every figure any of them uses comes from the same place and there is a single
server subprocess for the whole run.

Delegation
----------
Agents consult each other through `ask_*` tools. Each hop raises
`TeamDeps.depth`, and past `MAX_DELEGATION_DEPTH` the tool refuses rather
than running another agent. That is what stops two agents asking each other
the same question forever.

Specialists get a narrower set of colleagues than the Boss, matching the
prompts: Customer Service can reach Inventory and Accounting, but Facilities
has no reason to consult Customer Service about a lease.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext, UsageLimits

from . import audit, config
from .mcp_client import agent_toolset, build_toolset
from .models import AgentFinding, AgentName, TeamDeps

RUN_LIMITS = UsageLimits(
    request_limit=config.MAX_REQUESTS_PER_RUN,
    tool_calls_limit=config.MAX_TOOL_CALLS_PER_RUN,
)

# Who may ask whom. Narrow on purpose — an agent with four colleagues tends
# to delegate instead of using its own tools.
COLLEAGUES: dict[AgentName, list[AgentName]] = {
    AgentName.BOSS: [
        AgentName.INVENTORY,
        AgentName.ACCOUNTING,
        AgentName.FACILITIES,
        AgentName.CUSTOMER_SERVICE,
    ],
    AgentName.INVENTORY: [AgentName.ACCOUNTING, AgentName.CUSTOMER_SERVICE],
    AgentName.ACCOUNTING: [AgentName.INVENTORY, AgentName.FACILITIES],
    AgentName.FACILITIES: [AgentName.ACCOUNTING],
    AgentName.CUSTOMER_SERVICE: [AgentName.INVENTORY, AgentName.ACCOUNTING],
}

PROMPT_FILES = {
    AgentName.BOSS: "boss",
    AgentName.INVENTORY: "inventory",
    AgentName.ACCOUNTING: "accounting",
    AgentName.FACILITIES: "facilities",
    AgentName.CUSTOMER_SERVICE: "customer_service",
}


@dataclass
class AgentRun:
    """One completed agent run, with what the audit trail needs."""

    output: AgentFinding
    messages: list
    usage: object
    finish_reason: str | None


class Team:
    """The five agents, sharing one model and one MCP toolset.

    Built once per orchestrator run. Holding the toolset here means the MCP
    server starts once, not five times.
    """

    def __init__(self, toolset=None) -> None:
        self.model = config.build_model()
        # `toolset` lets the API share its already-open connection rather
        # than starting a second server subprocess.
        self.toolset = toolset if toolset is not None else build_toolset()
        self._owns_toolset = toolset is None
        # Agents get the filtered view: no decide_approval, no reset.
        self.agent_tools = agent_toolset(self.toolset)
        self.shared_rules = config.load_prompt("_shared_rules")
        self.agents: dict[AgentName, Agent] = {}
        self.model_calls = 0
        self.tool_calls = 0
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _instructions(self, name: AgentName) -> str:
        """Shared rules first, then the agent's own brief.

        Shared rules go first deliberately: they are the constraints, and a
        model that reads its job before its limits tends to weight the job
        more heavily.
        """
        return f"{self.shared_rules}\n\n---\n\n{config.load_prompt(PROMPT_FILES[name])}"

    def _build(self) -> None:
        for name in AgentName:
            agent = Agent(
                self.model,
                name=f"campus-{name.value}",
                instructions=self._instructions(name),
                output_type=AgentFinding,
                deps_type=TeamDeps,
                toolsets=[self.agent_tools],
            )
            self._add_context(agent, name)
            self._add_delegation(agent, name)
            self.agents[name] = agent

    def _add_context(self, agent: Agent, name: AgentName) -> None:
        """Per-run context, rebuilt on every request rather than baked in."""

        @agent.instructions
        def who_and_what(ctx: RunContext[TeamDeps]) -> str:
            d = ctx.deps
            lines = [
                "## This run",
                f"You are the **{name.value}** agent.",
                f"Working on ticket #{d.ticket_id}"
                + (f" (type: {d.ticket_type})." if d.ticket_type else "."),
            ]
            if d.depth > 0:
                lines.append(
                    f"You were asked for help by a colleague (delegation depth "
                    f"{d.depth} of {config.MAX_DELEGATION_DEPTH}). Answer the "
                    "specific question you were given and hand back — do not "
                    "take over the whole ticket."
                )
            remaining = config.MAX_DELEGATION_DEPTH - d.depth
            if remaining <= 0:
                lines.append(
                    "You have reached the delegation limit: you cannot ask a "
                    "colleague from here. Use your own tools and report what "
                    "you can establish."
                )
            lines.append(
                f"Set `agent` to '{name.value}' and `ticket_id` to {d.ticket_id} "
                "in your reply."
            )
            return "\n".join(lines)

    def _add_delegation(self, agent: Agent, name: AgentName) -> None:
        """Give this agent one `ask_<colleague>` tool per permitted colleague."""
        for colleague in COLLEAGUES[name]:
            self._register_ask_tool(agent, name, colleague)

    def _register_ask_tool(self, agent: Agent, asker: AgentName, colleague: AgentName) -> None:
        tool_name = f"ask_{colleague.value}"
        blurb = {
            AgentName.INVENTORY: "stock levels, restocking, vendors and purchase orders",
            AgentName.ACCOUNTING: "invoices, cash, payments, pricing and discounts",
            AgentName.FACILITIES: "the lease, rent and the premises",
            AgentName.CUSTOMER_SERVICE: "what to say to a customer",
            AgentName.BOSS: "overall priorities across tickets",
        }[colleague]

        async def ask(ctx: RunContext[TeamDeps], question: str) -> str:
            # The depth guard. Refuse rather than recurse.
            if ctx.deps.depth >= config.MAX_DELEGATION_DEPTH:
                return (
                    f"Delegation limit reached (depth {ctx.deps.depth}). "
                    f"{colleague.value} was not consulted. Answer with your own "
                    "tools and say in your report what you could not establish."
                )

            child = TeamDeps(
                ticket_id=ctx.deps.ticket_id,
                ticket_type=ctx.deps.ticket_type,
                acting_agent=colleague,
                depth=ctx.deps.depth + 1,
                run_id=ctx.deps.run_id,
            )
            result = await self.run_agent(
                colleague,
                task=question,
                deps=child,
                asked_by=asker,
            )
            f = result.output
            parts = [f"{colleague.value} says: {f.summary}"]
            if f.actions_taken:
                parts.append("Actions: " + "; ".join(f.actions_taken))
            if f.blocked_by:
                parts.append(f"Blocked by: {f.blocked_by}")
            if f.approval_ids:
                parts.append(f"Approvals raised: {f.approval_ids}")
            if f.draft_ids:
                parts.append(f"Drafts written: {f.draft_ids}")
            return " | ".join(parts)

        ask.__name__ = tool_name
        ask.__doc__ = (
            f"Ask the {colleague.value} agent about {blurb}.\n\n"
            "Use this only when the question genuinely belongs to them and "
            "your own tools cannot answer it. Ask one specific question.\n\n"
            "Args:\n    question: The specific question, including the ticket number."
        )
        agent.tool(ask, name=tool_name)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    async def run_agent(
        self,
        name: AgentName,
        task: str,
        deps: TeamDeps,
        asked_by: AgentName | None = None,
    ) -> AgentRun:
        """Run one agent and append the run to the audit trail.

        Every run is audited — including ones that fail — so the trail shows
        what was attempted, not just what succeeded.
        """
        started = audit.now_iso()
        agent = self.agents[name]

        try:
            result = await agent.run(task, deps=deps, usage_limits=RUN_LIMITS)
        except Exception as exc:
            audit.record(
                run_id=deps.run_id,
                agent=name.value,
                ticket_id=deps.ticket_id,
                task=task,
                started_at=started,
                status="error",
                stop_reason=(
                    "usage_limit_exceeded"
                    if "limit" in type(exc).__name__.lower()
                    else "error"
                ),
                depth=deps.depth,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

        messages = result.all_messages()
        finish_reason = None
        for msg in reversed(messages):
            reason = getattr(msg, "finish_reason", None)
            if reason is not None:
                finish_reason = str(reason)
                break

        usage = result.usage
        self.model_calls += getattr(usage, "requests", 0) or 0
        self.tool_calls += getattr(usage, "tool_calls", 0) or 0

        finding = result.output
        # The model fills these in, but the run knows better than the model.
        finding.agent = name
        finding.ticket_id = deps.ticket_id

        audit.record(
            run_id=deps.run_id,
            agent=name.value,
            ticket_id=deps.ticket_id,
            task=task if asked_by is None else f"[asked by {asked_by.value}] {task}",
            started_at=started,
            status="ok",
            stop_reason="completed",
            messages=messages,
            usage=usage,
            finish_reason=finish_reason,
            result_summary=finding.summary,
            delegated_to=[a.value for a in finding.delegated_to],
            depth=deps.depth,
        )

        return AgentRun(
            output=finding, messages=messages, usage=usage, finish_reason=finish_reason
        )

    async def __aenter__(self) -> "Team":
        # Only manage the connection if we opened it. When the API passes its
        # own toolset in, the API owns the lifecycle.
        if self._owns_toolset:
            await self.toolset.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._owns_toolset:
            await self.toolset.__aexit__(*exc)
