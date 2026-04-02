import subprocess
import sys
import time
import logging
import os

import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

SUBSTACK_RSS = "https://cryptohayes.substack.com/feed"
MEDIUM_RSS = "https://medium.com/feed/@cryptohayes"
LOOKBACK_DAYS = 30

LAST30DAYS_SCRIPT = os.path.expanduser(
    "~/.claude/skills/last30days/scripts/last30days.py"
)

# Cache for essays and social signal
_essay_cache = {"content": None, "fetched_at": 0}
_social_cache = {"content": None, "fetched_at": 0}

ESSAY_CACHE_TTL = 3600       # 1 hour
SOCIAL_CACHE_TTL = 1800      # 30 minutes

# Pre-cached file paths (written by cron)
CACHED_ESSAYS_PATH = "/tmp/arthur-essays.txt"
CACHED_SOCIAL_PATH = "/tmp/arthur-social-signal.txt"

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


def _parse_feed(url, source_name):
    """Fetch and parse an RSS feed, return posts from last 30 days."""
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        logger.warning("Error fetching %s: %s", source_name, e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    results = []

    for entry in feed.entries:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            continue

        if pub_date < cutoff:
            continue

        content = ""
        if hasattr(entry, "content"):
            raw_html = entry.content[0].value
            content = BeautifulSoup(raw_html, "html.parser").get_text(
                separator="\n", strip=True
            )
        elif hasattr(entry, "summary"):
            content = BeautifulSoup(entry.summary, "html.parser").get_text(
                separator="\n", strip=True
            )

        if len(content) > 3000:
            content = content[:3000] + "..."

        results.append({
            "source": source_name,
            "title": entry.get("title", "Untitled"),
            "url": entry.get("link", ""),
            "date": pub_date.strftime("%Y-%m-%d"),
            "body": content,
        })

    return results


def get_latest_hayes_essay():
    """Return the single most recent essay (backwards-compatible)."""
    essays = get_all_essays()
    if essays:
        return essays[0]
    return FALLBACK_ESSAY


def get_all_essays():
    """Fetch essays from Substack + Medium, cached for 1 hour."""
    now = time.time()
    if _essay_cache["content"] and now - _essay_cache["fetched_at"] < ESSAY_CACHE_TTL:
        return _essay_cache["content"]

    essays = []
    essays += _parse_feed(SUBSTACK_RSS, "Substack")
    essays += _parse_feed(MEDIUM_RSS, "Medium")
    essays.sort(key=lambda x: x["date"], reverse=True)

    if essays:
        _essay_cache["content"] = essays
        _essay_cache["fetched_at"] = now
        return essays

    # Try pre-cached file from cron
    if os.path.exists(CACHED_ESSAYS_PATH):
        try:
            with open(CACHED_ESSAYS_PATH) as f:
                cached = f.read().strip()
            if cached:
                _essay_cache["content"] = [{"source": "cached", "title": "Pre-cached essays", "date": "", "body": cached}]
                _essay_cache["fetched_at"] = now
                return _essay_cache["content"]
        except Exception:
            pass

    return [FALLBACK_ESSAY]


def get_social_signal():
    """Fetch Arthur Hayes social signal via last30days (X, Reddit, YouTube)."""
    now = time.time()
    if _social_cache["content"] and now - _social_cache["fetched_at"] < SOCIAL_CACHE_TTL:
        return _social_cache["content"]

    # Try pre-cached file first (faster)
    if os.path.exists(CACHED_SOCIAL_PATH):
        try:
            cache_age = now - os.path.getmtime(CACHED_SOCIAL_PATH)
            if cache_age < SOCIAL_CACHE_TTL:
                with open(CACHED_SOCIAL_PATH) as f:
                    cached = f.read().strip()
                if cached:
                    _social_cache["content"] = cached
                    _social_cache["fetched_at"] = now
                    return cached
        except Exception:
            pass

    # Run last30days live
    if not os.path.exists(LAST30DAYS_SCRIPT):
        logger.warning("last30days script not found at %s", LAST30DAYS_SCRIPT)
        return None

    try:
        result = subprocess.run(
            [
                sys.executable,
                LAST30DAYS_SCRIPT,
                "Arthur Hayes crypto macro bitcoin",
                "--emit", "compact",
                "--days", "30",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0 and result.stdout.strip():
            _social_cache["content"] = result.stdout.strip()
            _social_cache["fetched_at"] = now
            return _social_cache["content"]
    except subprocess.TimeoutExpired:
        logger.warning("last30days timed out")
    except Exception as e:
        logger.warning("last30days error: %s", e)

    return None


def format_essays_for_prompt(essays):
    """Format essays as context text for the LLM."""
    if not essays:
        return ""

    parts = []
    for e in essays[:5]:  # Cap at 5 most recent
        parts.append(
            f"### {e['title']}\n"
            f"**Source:** {e.get('source', 'Substack')} | **Date:** {e['date']}\n\n"
            f"{e['body'][:2000]}"
        )
    return "## Arthur Hayes Essays — Last 30 Days\n\n" + "\n\n---\n\n".join(parts)
