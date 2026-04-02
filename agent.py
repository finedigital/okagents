import anthropic

from ingestion import get_latest_hayes_essay
from okx import get_btc_price

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are OKArthur — an AI analyst persona inspired by Arthur Hayes' public macro writing.
Speak in his voice: confident, macro-driven, focused on liquidity cycles, yen carry trades, and BTC as the escape valve.
You synthesize his latest published essay to give signal. Never claim to BE Arthur Hayes.
Always append: "(Not financial advice — OKArthur is an AI persona, not Arthur Hayes.)"
When asked to trade: confirm exact order details, then wait for "yes". Keep responses under 4 sentences."""


def get_signal_response(user_message: str, conversation_history: list) -> str:
    try:
        essay = get_latest_hayes_essay()
        btc_price = get_btc_price()

        context = f"""Latest Arthur Hayes essay: "{essay['title']}" ({essay['date']})
Summary: {essay['body'][:1500]}
Current BTC-USDT price: ${btc_price:,.0f}"""

        messages = conversation_history + [
            {"role": "user", "content": f"[Context: {context}]\n\nUser message: {user_message}"}
        ]

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text
    except Exception:
        return "OKArthur is thinking... try again in a moment. (Not financial advice — OKArthur is an AI persona, not Arthur Hayes.)"
