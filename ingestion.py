import feedparser
import time

HAYES_RSS = "https://cryptohayes.substack.com/feed"

FALLBACK_ESSAY = {
    "title": "Dust on Crust",
    "date": "2024-03-18",
    "url": "https://cryptohayes.substack.com",
    "body": (
        "The BOJ ended negative interest rates and YCC but kept buying JGBs. "
        "The yen weakened because real rates are still deeply negative. "
        "Cheap yen funds the global carry trade, which ultimately flows into risk assets like BTC. "
        "The Fed will cut rates eventually, adding more dollar liquidity. "
        "BTC is the escape valve from fiat debasement. The macro setup is extremely bullish."
    ),
}

_cache = {"content": None, "fetched_at": 0}


def get_latest_hayes_essay():
    if time.time() - _cache["fetched_at"] < 3600:
        return _cache["content"]

    try:
        feed = feedparser.parse(HAYES_RSS)
        entry = feed.entries[0]
        _cache["content"] = {
            "title": entry.title,
            "date": entry.published,
            "url": entry.link,
            "body": entry.get("summary", "No content available"),
        }
        _cache["fetched_at"] = time.time()
        return _cache["content"]
    except Exception:
        return FALLBACK_ESSAY
