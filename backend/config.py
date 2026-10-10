"""Model and connection settings for the agent team.

Every agent runs on the same model through the same gateway, so this is the
one place either changes.

Configuration comes from the environment, never from source:

    PORTKEY_API_KEY   required — the gateway key
    MODEL_NAME        optional — defaults to the course model
    PORTKEY_BASE_URL  optional — defaults to the Portkey gateway
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# The .env may sit in this project or one level up with the other coursework.
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# Ceilings per agent run. Generous enough for a real multi-tool answer, tight
# enough that a confused loop stops rather than burning the budget.
MAX_REQUESTS_PER_RUN = 12
MAX_TOOL_CALLS_PER_RUN = 20

# How deep one agent may delegate to another before the chain is refused.
# Boss -> specialist -> colleague is two hops, which is enough for real work
# and short enough that two agents cannot ask each other forever.
MAX_DELEGATION_DEPTH = 2


class NotConfigured(RuntimeError):
    """Raised when the API key is missing, so callers can fail cleanly."""


def api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise NotConfigured(
            "PORTKEY_API_KEY is not set. Put it in a .env at the project root "
            "so the agents can reach the model."
        )
    return key


def is_configured() -> bool:
    """Whether an agent run could start, without building anything."""
    return bool(os.getenv("PORTKEY_API_KEY"))


def build_model():
    """One model instance, shared by all five agents.

    `reasoning_effort` is pinned to "none" because the gateway rejects the
    combination of function tools and any other value on
    /v1/chat/completions:

        "Function tools with reasoning_effort are not supported for
         gpt-6-luna-global ... set reasoning_effort to 'none'."

    Every agent here depends on tools, so this is not optional.
    """
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=api_key()),
        settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    )


def load_prompt(name: str) -> str:
    """Read an agent's system prompt from backend/prompts/<name>.md.

    Prompts live in markdown rather than Python so the shop's rules can be
    edited without touching code.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise NotConfigured(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
