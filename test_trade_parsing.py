"""Unit tests for trade intent parsing logic."""

import re
import pytest

# ---- Parsing logic extracted from bot.py ----

SUPPORTED_TOKENS = (
    "btc|eth|avax|sol|xrp|ada|doge|bnb|bch|ltc|link|uni|aave|"
    "matic|dot|shib|trx|usdt|usdc|fil|atom"
)


def parse_trade_intent(text: str):
    """Parse a trade intent from user text.

    Returns (action, amount, token) or None if no trade intent detected.
    token may be None if a trade was detected but the token was not identified.
    """
    lower = text.lower()

    # Phase A: detect action + amount
    trade_match = re.search(r"\b(buy|sell)\b.*?\$?(\d+(?:\.\d+)?)", lower)
    if not trade_match:
        return None

    action, amount = trade_match.groups()

    # Phase B: detect token anywhere in message
    token_matches = re.findall(rf"\b({SUPPORTED_TOKENS})\b", lower)
    token = None
    for t in token_matches:
        if t not in ("usdt", "usdc"):
            token = t
            break

    return (action, float(amount), token)


# ---- Tests ----


class TestBasicPatterns:
    """Standard patterns: buy/sell <amount> <token>"""

    def test_buy_dollar_btc(self):
        assert parse_trade_intent("buy $50 btc") == ("buy", 50.0, "btc")

    def test_buy_no_dollar_btc(self):
        assert parse_trade_intent("buy 50 btc") == ("buy", 50.0, "btc")

    def test_sell_dollar_eth(self):
        assert parse_trade_intent("sell $200 eth") == ("sell", 200.0, "eth")

    def test_buy_decimal_amount(self):
        assert parse_trade_intent("sell 10.5 doge") == ("sell", 10.5, "doge")

    def test_buy_100_xrp(self):
        assert parse_trade_intent("buy $100 xrp") == ("buy", 100.0, "xrp")

    def test_buy_100_sol(self):
        assert parse_trade_intent("buy 100 sol") == ("buy", 100.0, "sol")


class TestNaturalLanguageVariations:
    """Prepositions, word order, and phrasing variations."""

    def test_buy_in_avax(self):
        """The original bug: 'buy $50 in avax' was defaulting to BTC."""
        assert parse_trade_intent("buy $50 in avax") == ("buy", 50.0, "avax")

    def test_buy_of_eth(self):
        assert parse_trade_intent("buy $50 of eth") == ("buy", 50.0, "eth")

    def test_buy_worth_of_btc(self):
        assert parse_trade_intent("sell $200 worth of btc") == ("sell", 200.0, "btc")

    def test_token_before_amount(self):
        assert parse_trade_intent("buy avax $50") == ("buy", 50.0, "avax")

    def test_buy_in_avax_with_usdt(self):
        """Should pick avax, not usdt."""
        result = parse_trade_intent("buy $50 in avax with USDT")
        assert result == ("buy", 50.0, "avax")

    def test_buy_some_sol(self):
        assert parse_trade_intent("buy $100 some sol") == ("buy", 100.0, "sol")

    def test_sell_my_ada(self):
        assert parse_trade_intent("sell $75 ada please") == ("sell", 75.0, "ada")


class TestWithBotMention:
    """Messages that include @mention prefix."""

    def test_mention_buy_avax(self):
        assert parse_trade_intent("@OKArthurBot buy $50 in avax") == ("buy", 50.0, "avax")

    def test_mention_buy_btc(self):
        assert parse_trade_intent("@OKArthurBot buy $200 btc") == ("buy", 200.0, "btc")

    def test_mention_buy_avax_with_usdt(self):
        result = parse_trade_intent("@OKArthurBot buy $50 in avax with USDT")
        assert result == ("buy", 50.0, "avax")


class TestAllSupportedTokens:
    """Ensure every supported token (except stablecoins) is correctly detected."""

    @pytest.mark.parametrize("token", [
        "btc", "eth", "avax", "sol", "xrp", "ada", "doge", "bnb",
        "bch", "ltc", "link", "uni", "aave", "matic", "dot", "shib",
        "trx", "fil", "atom",
    ])
    def test_each_token(self, token):
        result = parse_trade_intent(f"buy $100 {token}")
        assert result == ("buy", 100.0, token)

    @pytest.mark.parametrize("token", [
        "btc", "eth", "avax", "sol", "xrp", "ada", "doge", "bnb",
        "bch", "ltc", "link", "uni", "aave", "matic", "dot", "shib",
        "trx", "fil", "atom",
    ])
    def test_each_token_with_preposition(self, token):
        result = parse_trade_intent(f"buy $100 in {token}")
        assert result == ("buy", 100.0, token)


class TestMissingToken:
    """When token is not specified, should return None for token."""

    def test_buy_amount_only(self):
        result = parse_trade_intent("buy $50")
        assert result == ("buy", 50.0, None)

    def test_sell_amount_only(self):
        result = parse_trade_intent("sell $200")
        assert result == ("sell", 200.0, None)


class TestNoTradeIntent:
    """Messages that are not trade requests."""

    def test_general_question(self):
        assert parse_trade_intent("what do you think about avax?") is None

    def test_empty_string(self):
        assert parse_trade_intent("") is None

    def test_greeting(self):
        assert parse_trade_intent("hello there") is None


class TestStablecoinFiltering:
    """USDT/USDC should be filtered out as quote currencies."""

    def test_usdt_only_returns_none(self):
        result = parse_trade_intent("buy $50 usdt")
        assert result == ("buy", 50.0, None)

    def test_usdc_only_returns_none(self):
        result = parse_trade_intent("buy $50 usdc")
        assert result == ("buy", 50.0, None)

    def test_avax_preferred_over_usdt(self):
        result = parse_trade_intent("buy $50 avax with usdt")
        assert result == ("buy", 50.0, "avax")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
