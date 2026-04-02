import os
import logging
import anthropic

from ingestion import (
    get_latest_hayes_essay,
    get_all_essays,
    get_social_signal,
    format_essays_for_prompt,
)
from okx import get_btc_price

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()

_soul_path = os.path.join(os.path.dirname(__file__), "SOUL.md")
with open(_soul_path) as _f:
    SYSTEM_PROMPT = _f.read()

RESEARCH_TRIGGERS = [
    "what does arthur",
    "arthur's view",
    "arthur's thesis",
    "arthur's take",
    "latest essay",
    "what did arthur",
    "current thesis",
    "right now",
    "today",
    "just posted",
    "new essay",
]


def should_research(message: str) -> bool:
    """Check if the message warrants a deep research pull."""
    msg_lower = message.lower()
    return any(trigger in msg_lower for trigger in RESEARCH_TRIGGERS)


def _build_context(user_message: str, deep: bool) -> str:
    """Build context string from available signal sources."""
    parts = []

    # BTC price — always included
    try:
        btc_price = get_btc_price()
        parts.append(f"Current BTC-USDT price: ${btc_price:,.0f}")
    except Exception:
        pass

    if deep:
        # Full research: all essays + social signal
        essays = get_all_essays()
        if essays:
            parts.append(format_essays_for_prompt(essays))

        social = get_social_signal()
        if social:
            parts.append(
                "## Arthur Hayes — Social & Video (Last 30 Days)\n\n" + social
            )
    else:
        # Standard: just the latest essay
        essay = get_latest_hayes_essay()
        parts.append(
            f'Latest Arthur Hayes essay: "{essay["title"]}" ({essay["date"]})\n'
            f'Summary: {essay["body"][:1500]}'
        )

    return "\n\n---\n\n".join(parts)


def get_signal_response(user_message: str, conversation_history: list) -> str:
    """Generate OKArthur's response. Returns (response_text, used_deep_research)."""
    try:
        deep = should_research(user_message)
        context = _build_context(user_message, deep)

        system = SYSTEM_PROMPT
        if deep:
            system += (
                "\n\n---\n\n"
                "## What Arthur Has Actually Said Recently\n"
                "Use the content below to inform your response. "
                "Draw from his actual words and thesis. "
                "Do not quote him verbatim — synthesize and speak in your voice.\n\n"
                + context
            )
            user_context = ""
        else:
            user_context = f"[Context: {context}]\n\n"

        messages = conversation_history + [
            {"role": "user", "content": f"{user_context}User message: {user_message}"}
        ]

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=system,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        logger.error("Signal response error: %s", e)
        return "OKArthur is thinking... try again in a moment."
