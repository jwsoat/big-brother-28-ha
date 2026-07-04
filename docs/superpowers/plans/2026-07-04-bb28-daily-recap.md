# BB28 Daily Recap Implementation Plan (Plan 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the standalone `bb28-daily-recap` service — a Vercel Cron function that scrapes 7 X accounts + 3 RSS feeds daily, extracts confirmed game facts with Claude, pushes those facts into the `big_brother_28` Home Assistant integration (built in Plan 1), summarizes the day into a 60+min talking-points outline with Claude, and emails it to the user before their livestream.

**Architecture:** Every network/SDK-touching operation (X login, RSS fetch, both Claude calls, the HA REST push, the Resend send) is a thin, dependency-injected wrapper with no logic of its own. All real logic — merging/sorting posts, building prompts, parsing Claude's JSON, building HA payloads, composing the email — lives in small pure-Python modules with zero I/O, fully unit-tested with plain `pytest` (no mocking framework, no live network, no live credentials needed to test). `pipeline.py` wires the pure logic to injected async functions and is itself tested by injecting fakes. The Vercel entry point (`api/daily-recap.py`) is the one place real clients get constructed — it has no automated test coverage (same accepted gap as Plan 1's HA glue code) and is verified by a manual smoke test after deployment with real secrets.

**Tech Stack:** Python (Vercel's classic Python runtime, `BaseHTTPRequestHandler` convention), `twikit` (X scraping), `feedparser` (RSS), `anthropic` (Claude SDK), `httpx` (async HTTP for the HA push), `resend` (email), `pytest`.

**Repo location:** This is a brand-new, separate repo from `big-brother-28-ha` (the Plan 1 HA integration). Working directory: `C:\Users\Jwsoat\Documents\Claude\bb28-daily-recap` (already created, currently empty). This plan document itself is kept alongside Plan 1's in the `big-brother-28-ha` repo (`docs/superpowers/specs/2026-07-03-daily-recap-and-sensor-expansion-design.md` is the spec both plans implement) purely so the two plans stay easy to find together — it describes work that happens in the *other* repo.

## Global Constraints

- Season start date: `2026-07-09`. Timezone: `America/Los_Angeles` (BB28 runs entirely within PDT, no DST edge case).
- Cron schedule: daily at 22:00 UTC (= 3pm PT).
- X sources (7): `TheBigBroTea`, `hamsterwatch`, `89razorskate20`, `BBFeedsFairy`, `rbbq`, `bigbrothernet`, `BBigBrotherBuzz`.
- RSS sources (3): `https://bigbrothernetwork.com/feed/`, `https://bigbrotherus.com/feed/`, `https://www.onlinebigbrother.com/feed/`.
- Recipient email: `info@jwsoat.com`. Subject format: `BB28 Daily Recap — Day N`.
- A source (X account or RSS feed) returning zero fresh items must produce a visible warning in the email, never a silent gap.
- HA push failures per-fact must be logged/skipped, never abort the summarize/email steps.
- Housemate statuses pushed to HA must be one of: `HOH`, `Nominated`, `Veto Competitor`, `Veto Winner`, `Eliminated` (from Plan 1's `HOUSEMATE_STATUSES` — `Safe` is a default, never an extracted fact).
- Extraction must only produce a fact when clearly and unambiguously stated — no guessing from jokes/speculation.
- New public GitHub repo for this project (per prior decision), default name `bb28-daily-recap` unless told otherwise.
- Secrets (Vercel env vars, never committed): `X_BURNER_USERNAME`, `X_BURNER_PASSWORD`, `X_BURNER_EMAIL`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `HA_BASE_URL`, `HA_LONG_LIVED_TOKEN`.
- This plan uses `vercel.json` (not `vercel.ts`) for the cron config — this project's Vercel config is a single `crons` array with no rewrites/redirects/headers, so a plain JSON file avoids requiring an `@vercel/config` npm install merely to declare one cron entry. Noted as a deliberate, scoped deviation from the platform's general "prefer vercel.ts" guidance, not an oversight.

---

### Task 1: Scaffold repo + shared models + config

**Files:**
- Create: `bb28_recap/__init__.py` (empty)
- Create: `bb28_recap/models.py`
- Create: `bb28_recap/config.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_config.py`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Produces: `models.RawPost(source: str, text: str, published_at: datetime)`, `models.SourceResult(source: str, posts: list[RawPost], found_any: bool)`, `models.Fact(fact_type: str, housemate: str = "", status: str = "", value: bool | None = None, sources: list[str] = [])`, `models.HAServiceCall(domain: str, service: str, data: dict)`, `models.PushResult(call: HAServiceCall, success: bool, error: str | None = None)`, `models.EmailContent(subject: str, body: str)` — every later task imports these exact names, don't redefine them elsewhere.
- Produces: `config.compute_day_number(today: date, start_date_str: str = config.BB28_START_DATE) -> int`, `config.load_env_config(env: dict) -> dict`, `config.MissingEnvVarError`, plus constants `config.BB28_START_DATE`, `config.BB28_TIMEZONE`, `config.RECIPIENT_EMAIL`, `config.X_ACCOUNTS`, `config.RSS_FEEDS`, `config.REQUIRED_ENV_VARS`.

- [ ] **Step 1: Create the directory structure and non-code scaffolding**

```bash
mkdir -p bb28_recap tests api
touch bb28_recap/__init__.py tests/__init__.py
```

Create `.gitignore`:
```
__pycache__/
*.pyc
.vercel
```

Create `requirements.txt`:
```
twikit
feedparser
anthropic
resend
httpx
```

Create `README.md`:
```markdown
# BB28 Daily Recap

Scrapes X + RSS for Big Brother 28 live-feed updates, extracts confirmed
game facts with Claude, pushes them into the `big_brother_28` Home Assistant
integration, and emails a 60+min talking-points outline before your livestream.

Runs daily via Vercel Cron at 22:00 UTC (3pm PT).

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create a Vercel project linked to this repo.
3. Set these environment variables in the Vercel dashboard (Production):
   - `X_BURNER_USERNAME`, `X_BURNER_PASSWORD`, `X_BURNER_EMAIL` — a dedicated
     burner X account's login, not your personal account.
   - `ANTHROPIC_API_KEY`
   - `RESEND_API_KEY`
   - `HA_BASE_URL` — your Home Assistant instance's public URL (reverse proxy).
   - `HA_LONG_LIVED_TOKEN` — a long-lived access token from your HA profile page.
4. Deploy. The cron is defined in `vercel.json`.

## Tests

`pytest tests/ -v` — all business logic is pure and unit-tested. The Vercel
entry point (`api/daily-recap.py`) has no automated tests (it's the one place
real network clients get constructed) — verify it manually after deploying
with real secrets.
```

- [ ] **Step 2: Write the failing test for config**

Create `tests/test_config.py`:

```python
from datetime import date

import pytest

from bb28_recap.config import (
    REQUIRED_ENV_VARS,
    MissingEnvVarError,
    compute_day_number,
    load_env_config,
)


def test_compute_day_number_is_1_on_start_date():
    assert compute_day_number(date(2026, 7, 9), "2026-07-09") == 1


def test_compute_day_number_increments_daily():
    assert compute_day_number(date(2026, 7, 12), "2026-07-09") == 4


def test_compute_day_number_is_0_before_start():
    assert compute_day_number(date(2026, 7, 1), "2026-07-09") == 0


def test_load_env_config_returns_all_required_values():
    env = {name: f"value-{name}" for name in REQUIRED_ENV_VARS}
    config = load_env_config(env)
    assert config == env


def test_load_env_config_raises_on_missing_vars():
    env = {name: f"value-{name}" for name in REQUIRED_ENV_VARS if name != "ANTHROPIC_API_KEY"}
    with pytest.raises(MissingEnvVarError, match="ANTHROPIC_API_KEY"):
        load_env_config(env)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.config'`

- [ ] **Step 4: Write models.py**

```python
"""Shared data types for the BB28 daily recap pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RawPost:
    source: str
    text: str
    published_at: datetime


@dataclass(frozen=True)
class SourceResult:
    source: str
    posts: list[RawPost]
    found_any: bool


@dataclass(frozen=True)
class Fact:
    fact_type: str  # "status" | "have_not" | "jury"
    housemate: str = ""
    status: str = ""  # only set when fact_type == "status"
    value: bool | None = None  # only set when fact_type in ("have_not", "jury")
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HAServiceCall:
    domain: str
    service: str
    data: dict


@dataclass(frozen=True)
class PushResult:
    call: HAServiceCall
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class EmailContent:
    subject: str
    body: str
```

- [ ] **Step 5: Write config.py**

```python
"""Config, constants, and the pure day-number computation for BB28 daily recap."""
from __future__ import annotations

from datetime import date

BB28_START_DATE = "2026-07-09"
BB28_TIMEZONE = "America/Los_Angeles"
RECIPIENT_EMAIL = "info@jwsoat.com"

X_ACCOUNTS = [
    "TheBigBroTea",
    "hamsterwatch",
    "89razorskate20",
    "BBFeedsFairy",
    "rbbq",
    "bigbrothernet",
    "BBigBrotherBuzz",
]

RSS_FEEDS = [
    "https://bigbrothernetwork.com/feed/",
    "https://bigbrotherus.com/feed/",
    "https://www.onlinebigbrother.com/feed/",
]

REQUIRED_ENV_VARS = [
    "X_BURNER_USERNAME",
    "X_BURNER_PASSWORD",
    "X_BURNER_EMAIL",
    "ANTHROPIC_API_KEY",
    "RESEND_API_KEY",
    "HA_BASE_URL",
    "HA_LONG_LIVED_TOKEN",
]


class MissingEnvVarError(RuntimeError):
    pass


def load_env_config(env: dict) -> dict:
    """Validate all required secrets are present; return them as a plain dict."""
    missing = [name for name in REQUIRED_ENV_VARS if not env.get(name)]
    if missing:
        raise MissingEnvVarError(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )
    return {name: env[name] for name in REQUIRED_ENV_VARS}


def compute_day_number(today: date, start_date_str: str = BB28_START_DATE) -> int:
    """Day 1 = start_date. Returns 0 if today is before start_date."""
    start = date.fromisoformat(start_date_str)
    delta = (today - start).days + 1
    return max(delta, 0)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Init git, create GitHub repo, commit**

```bash
git init -b main
git add -A
git commit -m "feat: scaffold bb28-daily-recap - shared models, config, day-number logic"
gh repo create bb28-daily-recap --public --source=. --remote=origin --push
```

---

### Task 2: Aggregate module (merge, sort, missing-source detection)

**Files:**
- Create: `bb28_recap/aggregate.py`
- Create: `tests/test_aggregate.py`

**Interfaces:**
- Consumes: `models.RawPost`, `models.SourceResult` (Task 1).
- Produces: `aggregate.aggregate_sources(results: list[SourceResult]) -> list[RawPost]`, `aggregate.missing_sources(results: list[SourceResult]) -> list[str]`, `aggregate.render_raw_feed_text(posts: list[RawPost]) -> str` — consumed by `pipeline.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_aggregate.py`:

```python
from datetime import datetime

from bb28_recap.aggregate import aggregate_sources, missing_sources, render_raw_feed_text
from bb28_recap.models import RawPost, SourceResult


def _post(source, text, hour):
    return RawPost(source=source, text=text, published_at=datetime(2026, 7, 10, hour, 0))


def test_aggregate_sources_merges_and_sorts_by_time():
    results = [
        SourceResult(source="x:a", posts=[_post("x:a", "second", 14)], found_any=True),
        SourceResult(source="rss:b", posts=[_post("rss:b", "first", 9)], found_any=True),
    ]
    posts = aggregate_sources(results)
    assert [p.text for p in posts] == ["first", "second"]


def test_aggregate_sources_handles_empty_results():
    assert aggregate_sources([]) == []


def test_missing_sources_returns_only_found_any_false():
    results = [
        SourceResult(source="x:a", posts=[_post("x:a", "hi", 9)], found_any=True),
        SourceResult(source="rss:b", posts=[], found_any=False),
    ]
    assert missing_sources(results) == ["rss:b"]


def test_missing_sources_empty_when_all_found():
    results = [SourceResult(source="x:a", posts=[_post("x:a", "hi", 9)], found_any=True)]
    assert missing_sources(results) == []


def test_render_raw_feed_text_formats_each_post():
    posts = [_post("x:a", "hello", 9)]
    text = render_raw_feed_text(posts)
    assert text == "[09:00] (x:a) hello"


def test_render_raw_feed_text_joins_multiple_lines():
    posts = [_post("x:a", "first", 9), _post("rss:b", "second", 14)]
    text = render_raw_feed_text(posts)
    assert text == "[09:00] (x:a) first\n[14:00] (rss:b) second"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.aggregate'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/aggregate.py`:

```python
"""Merge, sort, and flag gaps across all fetched sources."""
from __future__ import annotations

from .models import RawPost, SourceResult


def aggregate_sources(results: list[SourceResult]) -> list[RawPost]:
    """Merge all posts across sources into one list, sorted oldest to newest."""
    all_posts: list[RawPost] = []
    for result in results:
        all_posts.extend(result.posts)
    return sorted(all_posts, key=lambda p: p.published_at)


def missing_sources(results: list[SourceResult]) -> list[str]:
    """Sources that returned zero posts - candidates for a 'possible scrape break' warning."""
    return [r.source for r in results if not r.found_any]


def render_raw_feed_text(posts: list[RawPost]) -> str:
    """Flatten into one text blob for the LLM prompt, each line tagged with source+time."""
    lines = [
        f"[{p.published_at.strftime('%H:%M')}] ({p.source}) {p.text}" for p in posts
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/aggregate.py tests/test_aggregate.py
git commit -m "feat: add aggregate module - merge/sort posts, detect missing sources"
git push
```

---

### Task 3: RSS source module

**Files:**
- Create: `bb28_recap/sources_rss.py`
- Create: `tests/test_sources_rss.py`

**Interfaces:**
- Consumes: `models.RawPost`, `models.SourceResult` (Task 1).
- Produces: `sources_rss.filter_recent_entries(entries: list[dict], now: datetime, window: timedelta = timedelta(hours=24)) -> list[RawPost]`, `sources_rss.fetch_rss_source(feed_url: str, now: datetime) -> SourceResult` — consumed by `api/daily-recap.py` (Task 10).

**Test approach:** `feedparser.parse()` accepts either a URL or a raw feed string (it auto-detects). This lets `fetch_rss_source` get one real, no-network, no-mocking test by handing it a hand-written RSS XML string instead of a URL.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sources_rss.py`:

```python
import time
from datetime import datetime, timedelta, timezone

from bb28_recap.sources_rss import fetch_rss_source, filter_recent_entries

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Sample BB Feed</title>
<item>
  <title>Recent Update</title>
  <description>Something happened today</description>
  <pubDate>{recent_date}</pubDate>
</item>
<item>
  <title>Old Update</title>
  <description>Something happened last week</description>
  <pubDate>{old_date}</pubDate>
</item>
</channel></rss>"""


def _rfc822(dt):
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def test_filter_recent_entries_excludes_entries_older_than_window():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    recent = time.struct_time((2026, 7, 10, 9, 0, 0, 0, 0, 0))
    old = time.struct_time((2026, 7, 1, 9, 0, 0, 0, 0, 0))
    entries = [
        {"title": "Recent", "summary": "", "published_parsed": recent},
        {"title": "Old", "summary": "", "published_parsed": old},
    ]
    posts = filter_recent_entries(entries, now)
    assert [p.text for p in posts] == ["Recent"]


def test_filter_recent_entries_skips_entries_with_no_published_date():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    entries = [{"title": "No date", "summary": "", "published_parsed": None}]
    assert filter_recent_entries(entries, now) == []


def test_filter_recent_entries_combines_title_and_summary():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    recent = time.struct_time((2026, 7, 10, 9, 0, 0, 0, 0, 0))
    entries = [{"title": "Title", "summary": "Body", "published_parsed": recent}]
    posts = filter_recent_entries(entries, now)
    assert posts[0].text == "Title: Body"


def test_fetch_rss_source_parses_real_feed_content_and_filters_and_tags():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    xml = SAMPLE_RSS.format(
        recent_date=_rfc822(datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)),
        old_date=_rfc822(datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)),
    )
    result = fetch_rss_source(xml, now)
    assert result.found_any is True
    assert len(result.posts) == 1
    assert result.posts[0].source.startswith("rss:")
    assert "Recent Update" in result.posts[0].text


def test_fetch_rss_source_found_any_false_when_nothing_recent():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    xml = SAMPLE_RSS.format(
        recent_date=_rfc822(datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)),
        old_date=_rfc822(datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)),
    )
    result = fetch_rss_source(xml, now)
    assert result.found_any is False
    assert result.posts == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sources_rss.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.sources_rss'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/sources_rss.py`:

```python
"""Fetch and filter RSS feed entries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import feedparser

from .models import RawPost, SourceResult


def filter_recent_entries(
    entries: list[dict], now: datetime, window: timedelta = timedelta(hours=24)
) -> list[RawPost]:
    cutoff = now - window
    posts = []
    for entry in entries:
        published_struct = entry.get("published_parsed")
        if published_struct is None:
            continue
        published_at = datetime(*published_struct[:6], tzinfo=timezone.utc)
        if published_at < cutoff:
            continue
        text = entry.get("title", "")
        summary = entry.get("summary", "")
        if summary:
            text = f"{text}: {summary}"
        posts.append(RawPost(source="", text=text, published_at=published_at))
    return posts


def fetch_rss_source(feed_url: str, now: datetime) -> SourceResult:
    parsed = feedparser.parse(feed_url)
    raw_posts = filter_recent_entries(parsed.entries, now)
    tagged_posts = [
        RawPost(source=f"rss:{feed_url}", text=p.text, published_at=p.published_at)
        for p in raw_posts
    ]
    return SourceResult(
        source=f"rss:{feed_url}", posts=tagged_posts, found_any=bool(tagged_posts)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sources_rss.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/sources_rss.py tests/test_sources_rss.py
git commit -m "feat: add RSS source module - fetch, filter to last 24h, tag by source"
git push
```

---

### Task 4: X source module

**Files:**
- Create: `bb28_recap/sources_x.py`
- Create: `tests/test_sources_x.py`

**Interfaces:**
- Consumes: `models.RawPost`, `models.SourceResult` (Task 1).
- Produces: `sources_x.filter_recent_posts(raw_posts: list[tuple[str, datetime]], now: datetime, window: timedelta = timedelta(hours=24)) -> list[tuple[str, datetime]]`, `sources_x.fetch_x_source(client, account: str, now: datetime) -> SourceResult` (async) — `client` must expose an async `get_user_tweets(account: str) -> list[tuple[str, datetime]]` method; consumed by `api/daily-recap.py` (Task 10), which supplies a real `twikit`-backed client.

**Test approach:** tests pass a small `FakeClient` class instead of a real `twikit.Client` — no network, no credentials needed. Call the async function via `asyncio.run(...)` directly in the test; no `pytest-asyncio` dependency needed for one coroutine per test.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sources_x.py`:

```python
import asyncio
from datetime import datetime, timezone

from bb28_recap.sources_x import fetch_x_source, filter_recent_posts


class FakeClient:
    def __init__(self, tweets):
        self._tweets = tweets

    async def get_user_tweets(self, account):
        return self._tweets


def test_filter_recent_posts_excludes_old_posts():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    posts = [
        ("recent", datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)),
        ("old", datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)),
    ]
    result = filter_recent_posts(posts, now)
    assert [text for text, _ in result] == ["recent"]


def test_filter_recent_posts_empty_input():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    assert filter_recent_posts([], now) == []


def test_fetch_x_source_tags_and_filters_via_injected_client():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    client = FakeClient(
        [
            ("recent tweet", datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)),
            ("old tweet", datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)),
        ]
    )
    result = asyncio.run(fetch_x_source(client, "SomeAccount", now))
    assert result.found_any is True
    assert len(result.posts) == 1
    assert result.posts[0].source == "x:SomeAccount"
    assert result.posts[0].text == "recent tweet"


def test_fetch_x_source_found_any_false_when_nothing_recent():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    client = FakeClient([("old tweet", datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc))])
    result = asyncio.run(fetch_x_source(client, "SomeAccount", now))
    assert result.found_any is False
    assert result.posts == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sources_x.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.sources_x'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/sources_x.py`:

```python
"""Fetch and filter X (Twitter) posts via an injected client."""
from __future__ import annotations

from datetime import datetime, timedelta

from .models import RawPost, SourceResult


def filter_recent_posts(
    raw_posts: list[tuple[str, datetime]],
    now: datetime,
    window: timedelta = timedelta(hours=24),
) -> list[tuple[str, datetime]]:
    cutoff = now - window
    return [(text, ts) for text, ts in raw_posts if ts >= cutoff]


async def fetch_x_source(client, account: str, now: datetime) -> SourceResult:
    """client must expose an async get_user_tweets(account) -> list[(text, datetime)]."""
    raw = await client.get_user_tweets(account)
    recent = filter_recent_posts(raw, now)
    posts = [
        RawPost(source=f"x:{account}", text=text, published_at=ts) for text, ts in recent
    ]
    return SourceResult(source=f"x:{account}", posts=posts, found_any=bool(posts))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sources_x.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/sources_x.py tests/test_sources_x.py
git commit -m "feat: add X source module - inject-able client, filter to last 24h, tag by source"
git push
```

---

### Task 5: Claude extraction module (structured fact extraction)

**Files:**
- Create: `bb28_recap/extract.py`
- Create: `tests/test_extract.py`

**Interfaces:**
- Consumes: `models.Fact` (Task 1).
- Produces: `extract.EXTRACTION_SYSTEM_PROMPT` (str constant), `extract.build_extraction_prompt(raw_feed_text: str) -> str`, `extract.parse_extraction_response(response_text: str) -> list[Fact]`, `extract.InvalidExtractionResponseError` — consumed by `pipeline.py` (Task 9) and `api/daily-recap.py` (Task 10, which supplies the real Claude API call).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_extract.py`:

```python
import json

import pytest

from bb28_recap.extract import (
    InvalidExtractionResponseError,
    build_extraction_prompt,
    parse_extraction_response,
)


def test_build_extraction_prompt_includes_raw_feed_text():
    prompt = build_extraction_prompt("[09:00] (x:a) Alex won HOH")
    assert "Alex won HOH" in prompt


def test_parse_extraction_response_parses_status_fact():
    response = json.dumps(
        [{"housemate": "Alex", "fact_type": "status", "status": "HOH", "sources": ["x:a"]}]
    )
    facts = parse_extraction_response(response)
    assert len(facts) == 1
    assert facts[0].housemate == "Alex"
    assert facts[0].fact_type == "status"
    assert facts[0].status == "HOH"
    assert facts[0].sources == ["x:a"]


def test_parse_extraction_response_parses_have_not_fact():
    response = json.dumps(
        [{"housemate": "Jordan", "fact_type": "have_not", "value": True, "sources": ["rss:b"]}]
    )
    facts = parse_extraction_response(response)
    assert facts[0].fact_type == "have_not"
    assert facts[0].value is True


def test_parse_extraction_response_parses_jury_fact():
    response = json.dumps(
        [{"housemate": "Sam", "fact_type": "jury", "value": True, "sources": ["x:a"]}]
    )
    facts = parse_extraction_response(response)
    assert facts[0].fact_type == "jury"
    assert facts[0].value is True


def test_parse_extraction_response_empty_array_returns_empty_list():
    assert parse_extraction_response("[]") == []


def test_parse_extraction_response_raises_on_invalid_json():
    with pytest.raises(InvalidExtractionResponseError):
        parse_extraction_response("not json")


def test_parse_extraction_response_raises_on_non_array():
    with pytest.raises(InvalidExtractionResponseError):
        parse_extraction_response(json.dumps({"not": "a list"}))


def test_parse_extraction_response_raises_on_unknown_fact_type():
    response = json.dumps([{"housemate": "Alex", "fact_type": "bogus"}])
    with pytest.raises(InvalidExtractionResponseError):
        parse_extraction_response(response)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.extract'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/extract.py`:

```python
"""Build the extraction prompt and parse Claude's structured JSON response."""
from __future__ import annotations

import json

from .models import Fact

EXTRACTION_SYSTEM_PROMPT = (
    "You are extracting confirmed Big Brother game facts from live-feed update posts. "
    "Only extract a fact if it is clearly and unambiguously stated as having happened - "
    "never guess, infer from jokes, or extract speculation/predictions. "
    "Return ONLY a JSON array, no other text. Each element must have exactly these keys: "
    '"housemate" (string), "fact_type" (one of "status", "have_not", "jury"), '
    '"status" (string, required when fact_type is "status", one of: HOH, Nominated, '
    'Veto Competitor, Veto Winner, Eliminated - omit for other fact_types), '
    '"value" (boolean, required when fact_type is "have_not" or "jury" - omit for "status"), '
    '"sources" (array of strings - which source tags in the feed stated this fact). '
    "If no facts are clearly stated, return an empty array []."
)


def build_extraction_prompt(raw_feed_text: str) -> str:
    return (
        "Here is today's raw Big Brother live-feed update text, "
        "each line tagged with its source and time:\n\n"
        f"{raw_feed_text}\n\n"
        "Extract the confirmed facts as a JSON array per your instructions."
    )


class InvalidExtractionResponseError(ValueError):
    pass


def parse_extraction_response(response_text: str) -> list[Fact]:
    try:
        raw_facts = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise InvalidExtractionResponseError(
            f"Claude extraction response was not valid JSON: {exc}"
        ) from exc

    if not isinstance(raw_facts, list):
        raise InvalidExtractionResponseError("Claude extraction response was not a JSON array")

    facts = []
    for item in raw_facts:
        fact_type = item.get("fact_type")
        if fact_type not in ("status", "have_not", "jury"):
            raise InvalidExtractionResponseError(f"Unknown fact_type: {fact_type!r}")
        facts.append(
            Fact(
                fact_type=fact_type,
                housemate=item.get("housemate", ""),
                status=item.get("status", ""),
                value=item.get("value"),
                sources=item.get("sources", []),
            )
        )
    return facts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_extract.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/extract.py tests/test_extract.py
git commit -m "feat: add extraction module - prompt builder + strict JSON fact parser"
git push
```

---

### Task 6: HA push module

**Files:**
- Create: `bb28_recap/ha_push.py`
- Create: `tests/test_ha_push.py`

**Interfaces:**
- Consumes: `models.Fact`, `models.HAServiceCall`, `models.PushResult` (Task 1).
- Produces: `ha_push.build_ha_service_calls(facts: list[Fact]) -> list[HAServiceCall]`, `ha_push.push_service_calls(session, base_url: str, token: str, calls: list[HAServiceCall]) -> list[PushResult]` (async) — `session` must expose an async `post(url, json, headers) -> response` method where `response` has a `.status` attribute; consumed by `pipeline.py` (Task 9) and `api/daily-recap.py` (Task 10, which supplies a real `httpx.AsyncClient`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_push.py`:

```python
import asyncio

from bb28_recap.ha_push import build_ha_service_calls, push_service_calls
from bb28_recap.models import Fact, HAServiceCall


class FakeResponse:
    def __init__(self, status):
        self.status = status


class FakeSession:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    async def post(self, url, json, headers):
        self.calls.append((url, json, headers))
        result = self._responses[len(self.calls) - 1]
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


def test_build_ha_service_calls_maps_status_fact():
    facts = [Fact(fact_type="status", housemate="Alex", status="HOH", sources=["x:a"])]
    calls = build_ha_service_calls(facts)
    assert calls == [
        HAServiceCall(
            domain="big_brother_28",
            service="set_housemate_status",
            data={"name": "Alex", "status": "HOH"},
        )
    ]


def test_build_ha_service_calls_maps_have_not_fact():
    facts = [Fact(fact_type="have_not", housemate="Jordan", value=True)]
    calls = build_ha_service_calls(facts)
    assert calls == [
        HAServiceCall(
            domain="big_brother_28",
            service="set_have_not",
            data={"name": "Jordan", "is_have_not": True},
        )
    ]


def test_build_ha_service_calls_maps_jury_fact():
    facts = [Fact(fact_type="jury", housemate="Sam", value=True)]
    calls = build_ha_service_calls(facts)
    assert calls == [
        HAServiceCall(
            domain="big_brother_28",
            service="set_jury_status",
            data={"name": "Sam", "is_jury_member": True},
        )
    ]


def test_push_service_calls_reports_success():
    calls = [HAServiceCall(domain="big_brother_28", service="set_housemate_status", data={})]
    session = FakeSession([200])
    results = asyncio.run(push_service_calls(session, "https://ha.example.com", "tok", calls))
    assert results[0].success is True
    assert results[0].error is None


def test_push_service_calls_reports_http_error_without_raising():
    calls = [HAServiceCall(domain="big_brother_28", service="set_housemate_status", data={})]
    session = FakeSession([500])
    results = asyncio.run(push_service_calls(session, "https://ha.example.com", "tok", calls))
    assert results[0].success is False
    assert "500" in results[0].error


def test_push_service_calls_isolates_a_raised_exception_per_call():
    calls = [
        HAServiceCall(domain="big_brother_28", service="set_housemate_status", data={}),
        HAServiceCall(domain="big_brother_28", service="set_have_not", data={}),
    ]
    session = FakeSession([ConnectionError("network down"), 200])
    results = asyncio.run(push_service_calls(session, "https://ha.example.com", "tok", calls))
    assert results[0].success is False
    assert "network down" in results[0].error
    assert results[1].success is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ha_push.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.ha_push'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/ha_push.py`:

```python
"""Turn extracted facts into HA REST service-call payloads and push them."""
from __future__ import annotations

from .models import Fact, HAServiceCall, PushResult


def build_ha_service_calls(facts: list[Fact]) -> list[HAServiceCall]:
    calls = []
    for fact in facts:
        if fact.fact_type == "status":
            calls.append(
                HAServiceCall(
                    domain="big_brother_28",
                    service="set_housemate_status",
                    data={"name": fact.housemate, "status": fact.status},
                )
            )
        elif fact.fact_type == "have_not":
            calls.append(
                HAServiceCall(
                    domain="big_brother_28",
                    service="set_have_not",
                    data={"name": fact.housemate, "is_have_not": bool(fact.value)},
                )
            )
        elif fact.fact_type == "jury":
            calls.append(
                HAServiceCall(
                    domain="big_brother_28",
                    service="set_jury_status",
                    data={"name": fact.housemate, "is_jury_member": bool(fact.value)},
                )
            )
    return calls


async def push_service_calls(
    session, base_url: str, token: str, calls: list[HAServiceCall]
) -> list[PushResult]:
    """session must expose an async post(url, json, headers) -> response with .status."""
    results = []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for call in calls:
        url = f"{base_url}/api/services/{call.domain}/{call.service}"
        try:
            response = await session.post(url, json=call.data, headers=headers)
            if response.status >= 400:
                results.append(
                    PushResult(call=call, success=False, error=f"HTTP {response.status}")
                )
            else:
                results.append(PushResult(call=call, success=True))
        except Exception as exc:  # noqa: BLE001 - any per-call failure is isolated, not fatal
            results.append(PushResult(call=call, success=False, error=str(exc)))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ha_push.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/ha_push.py tests/test_ha_push.py
git commit -m "feat: add HA push module - build service-call payloads, push with per-call isolation"
git push
```

---

### Task 7: Claude summarization module

**Files:**
- Create: `bb28_recap/summarize.py`
- Create: `tests/test_summarize.py`

**Interfaces:**
- Consumes: `models.Fact` (Task 1).
- Produces: `summarize.SUMMARY_SYSTEM_PROMPT` (str constant), `summarize.render_facts_text(facts: list[Fact]) -> str`, `summarize.build_summary_prompt(raw_feed_text: str, facts_text: str) -> str` — consumed by `pipeline.py` (Task 9) and `api/daily-recap.py` (Task 10, which supplies the real Claude API call).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_summarize.py`:

```python
from bb28_recap.models import Fact
from bb28_recap.summarize import build_summary_prompt, render_facts_text


def test_render_facts_text_formats_status_fact():
    facts = [Fact(fact_type="status", housemate="Alex", status="HOH", sources=["x:a"])]
    text = render_facts_text(facts)
    assert text == "- Alex: HOH (sources: x:a)"


def test_render_facts_text_formats_have_not_fact():
    facts = [Fact(fact_type="have_not", housemate="Jordan", value=True, sources=["rss:b"])]
    text = render_facts_text(facts)
    assert text == "- Jordan: have_not=True (sources: rss:b)"


def test_render_facts_text_handles_empty_list():
    assert render_facts_text([]) == "(no clearly-confirmed facts today)"


def test_build_summary_prompt_includes_both_blobs():
    prompt = build_summary_prompt("raw feed text here", "facts text here")
    assert "raw feed text here" in prompt
    assert "facts text here" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_summarize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.summarize'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/summarize.py`:

```python
"""Build the daily talking-points-outline prompt for Claude."""
from __future__ import annotations

from .models import Fact

SUMMARY_SYSTEM_PROMPT = (
    "You are writing a talking-points outline for a Big Brother fan podcast host "
    "to read from during a 60+ minute livestream. Structure it into these segments: "
    "Overnight Recap, HOH and Nominations, Veto, Showmances, House Drama, "
    "Predictions and Wrap-up. Each segment should have enough bullet points to "
    "sustain several minutes of commentary. Write bullet points, not a word-for-word "
    "script - the host will speak naturally from them."
)


def render_facts_text(facts: list[Fact]) -> str:
    if not facts:
        return "(no clearly-confirmed facts today)"
    lines = []
    for fact in facts:
        if fact.fact_type == "status":
            lines.append(f"- {fact.housemate}: {fact.status} (sources: {', '.join(fact.sources)})")
        else:
            lines.append(
                f"- {fact.housemate}: {fact.fact_type}={fact.value} "
                f"(sources: {', '.join(fact.sources)})"
            )
    return "\n".join(lines)


def build_summary_prompt(raw_feed_text: str, facts_text: str) -> str:
    return (
        "Today's raw live-feed update text:\n\n"
        f"{raw_feed_text}\n\n"
        "Confirmed facts extracted from today's feed:\n\n"
        f"{facts_text}\n\n"
        "Write today's talking-points outline per your instructions."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_summarize.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/summarize.py tests/test_summarize.py
git commit -m "feat: add summarization module - facts renderer + outline prompt builder"
git push
```

---

### Task 8: Email content module

**Files:**
- Create: `bb28_recap/email_content.py`
- Create: `tests/test_email_content.py`

**Interfaces:**
- Consumes: `models.EmailContent`, `models.PushResult` (Task 1), `config.compute_day_number` (Task 1, used by the caller, not this module directly).
- Produces: `email_content.render_applied_updates(push_results: list[PushResult]) -> str`, `email_content.render_source_warnings(missing_sources_list: list[str]) -> str`, `email_content.build_email_content(day_number: int, outline: str, push_results: list[PushResult], missing_sources_list: list[str]) -> EmailContent` — consumed by `pipeline.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_email_content.py`:

```python
from bb28_recap.email_content import (
    build_email_content,
    render_applied_updates,
    render_source_warnings,
)
from bb28_recap.models import HAServiceCall, PushResult


def test_render_applied_updates_formats_status_update():
    results = [
        PushResult(
            call=HAServiceCall(
                domain="big_brother_28",
                service="set_housemate_status",
                data={"name": "Alex", "status": "HOH"},
            ),
            success=True,
        )
    ]
    text = render_applied_updates(results)
    assert text == "Auto-updated: Alex → HOH"


def test_render_applied_updates_skips_failed_pushes():
    results = [
        PushResult(
            call=HAServiceCall(
                domain="big_brother_28",
                service="set_housemate_status",
                data={"name": "Alex", "status": "HOH"},
            ),
            success=False,
            error="HTTP 500",
        )
    ]
    assert render_applied_updates(results) == "No sensor updates applied today."


def test_render_applied_updates_empty_list():
    assert render_applied_updates([]) == "No sensor updates applied today."


def test_render_source_warnings_empty_when_no_missing_sources():
    assert render_source_warnings([]) == ""


def test_render_source_warnings_lists_each_missing_source():
    text = render_source_warnings(["x:a", "rss:b"])
    assert "x:a" in text
    assert "rss:b" in text
    assert "possible scrape break" in text


def test_build_email_content_subject_includes_day_number():
    content = build_email_content(5, "outline text", [], [])
    assert content.subject == "BB28 Daily Recap — Day 5"


def test_build_email_content_body_includes_outline_and_updates():
    results = [
        PushResult(
            call=HAServiceCall(
                domain="big_brother_28",
                service="set_housemate_status",
                data={"name": "Alex", "status": "HOH"},
            ),
            success=True,
        )
    ]
    content = build_email_content(5, "outline text here", results, [])
    assert "outline text here" in content.body
    assert "Auto-updated: Alex → HOH" in content.body


def test_build_email_content_body_includes_warnings_when_present():
    content = build_email_content(5, "outline", [], ["x:a"])
    assert "x:a" in content.body
    assert "possible scrape break" in content.body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_email_content.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.email_content'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/email_content.py`:

```python
"""Compose the daily recap email's subject and body."""
from __future__ import annotations

from .models import EmailContent, PushResult


def render_applied_updates(push_results: list[PushResult]) -> str:
    lines = []
    for result in push_results:
        if not result.success:
            continue
        data = result.call.data
        if result.call.service == "set_housemate_status":
            lines.append(f"Auto-updated: {data['name']} → {data['status']}")
        elif result.call.service == "set_have_not":
            lines.append(f"Auto-updated: {data['name']} have-not → {data['is_have_not']}")
        elif result.call.service == "set_jury_status":
            lines.append(f"Auto-updated: {data['name']} jury → {data['is_jury_member']}")
    if not lines:
        return "No sensor updates applied today."
    return "\n".join(lines)


def render_source_warnings(missing_sources_list: list[str]) -> str:
    if not missing_sources_list:
        return ""
    warnings = [
        f"⚠ No fresh posts/entries found for {source} — possible scrape break"
        for source in missing_sources_list
    ]
    return "\n".join(warnings)


def build_email_content(
    day_number: int,
    outline: str,
    push_results: list[PushResult],
    missing_sources_list: list[str],
) -> EmailContent:
    subject = f"BB28 Daily Recap — Day {day_number}"
    sections = [outline, "", "---", "", render_applied_updates(push_results)]
    warnings_text = render_source_warnings(missing_sources_list)
    if warnings_text:
        sections += ["", warnings_text]
    body = "\n".join(sections)
    return EmailContent(subject=subject, body=body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_email_content.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add bb28_recap/email_content.py tests/test_email_content.py
git commit -m "feat: add email content module - subject, applied-updates and warnings rendering"
git push
```

---

### Task 9: Pipeline orchestration

**Files:**
- Create: `bb28_recap/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `aggregate.aggregate_sources`, `aggregate.missing_sources`, `aggregate.render_raw_feed_text` (Task 2); `extract.build_extraction_prompt`, `extract.parse_extraction_response` (Task 5); `summarize.build_summary_prompt`, `summarize.render_facts_text` (Task 7); `email_content.build_email_content` (Task 8); `config.compute_day_number`, `config.BB28_TIMEZONE` (Task 1); `models.SourceResult`, `models.PushResult` (Task 1). Day number is computed from `now` converted into `BB28_TIMEZONE` (not raw UTC) — the spec requires the day count to follow PT, not wherever the Vercel function's clock happens to be.
- Produces: `pipeline.run_daily_recap(now, fetch_rss_sources, fetch_x_sources, call_claude_extract, call_claude_summarize, push_facts_to_ha, send_email) -> EmailContent` (async) — consumed by `api/daily-recap.py` (Task 10). All 6 callables are injected dependencies; their exact shapes are documented in the Step 3 code below.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
import asyncio
from datetime import datetime, timezone

from bb28_recap.models import RawPost, SourceResult
from bb28_recap.pipeline import run_daily_recap


def _make_deps(
    rss_results=None,
    x_results=None,
    extraction_response="[]",
    summary_response="outline text",
    push_results=None,
    raise_on_rss=False,
    raise_on_x=False,
):
    sent_emails = []

    async def fetch_rss_sources():
        if raise_on_rss:
            raise ConnectionError("rss down")
        return rss_results or []

    async def fetch_x_sources():
        if raise_on_x:
            raise ConnectionError("x down")
        return x_results or []

    async def call_claude_extract(prompt):
        return extraction_response

    async def call_claude_summarize(prompt):
        return summary_response

    async def push_facts_to_ha(facts):
        return push_results or []

    async def send_email(content):
        sent_emails.append(content)

    return (
        fetch_rss_sources,
        fetch_x_sources,
        call_claude_extract,
        call_claude_summarize,
        push_facts_to_ha,
        send_email,
        sent_emails,
    )


def test_happy_path_sends_email_with_correct_day_and_outline():
    now = datetime(2026, 7, 12, 15, 0, tzinfo=timezone.utc)
    post = RawPost(source="x:a", text="Alex won HOH", published_at=now)
    rss_results = []
    x_results = [SourceResult(source="x:a", posts=[post], found_any=True)]
    deps = _make_deps(rss_results=rss_results, x_results=x_results, summary_response="Today's outline")
    *fns, sent_emails = deps
    result = asyncio.run(run_daily_recap(now, *fns))
    assert result.subject == "BB28 Daily Recap — Day 4"
    assert "Today's outline" in result.body
    assert sent_emails == [result]


def test_rss_fetch_failure_does_not_abort_the_run():
    now = datetime(2026, 7, 12, 15, 0, tzinfo=timezone.utc)
    post = RawPost(source="x:a", text="Alex won HOH", published_at=now)
    x_results = [SourceResult(source="x:a", posts=[post], found_any=True)]
    deps = _make_deps(x_results=x_results, raise_on_rss=True)
    *fns, sent_emails = deps
    result = asyncio.run(run_daily_recap(now, *fns))
    assert len(sent_emails) == 1


def test_x_fetch_failure_does_not_abort_the_run():
    now = datetime(2026, 7, 12, 15, 0, tzinfo=timezone.utc)
    post = RawPost(source="rss:b", text="Jordan nominated", published_at=now)
    rss_results = [SourceResult(source="rss:b", posts=[post], found_any=True)]
    deps = _make_deps(rss_results=rss_results, raise_on_x=True)
    *fns, sent_emails = deps
    result = asyncio.run(run_daily_recap(now, *fns))
    assert len(sent_emails) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bb28_recap.pipeline'`

- [ ] **Step 3: Write the implementation**

Create `bb28_recap/pipeline.py`:

```python
"""Orchestrate the full daily recap pipeline. Zero direct network/SDK calls -
every I/O operation is an injected async callable, making this fully testable
with fakes."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .aggregate import aggregate_sources, missing_sources, render_raw_feed_text
from .config import BB28_TIMEZONE, compute_day_number
from .email_content import build_email_content
from .extract import build_extraction_prompt, parse_extraction_response
from .models import EmailContent, SourceResult
from .summarize import build_summary_prompt, render_facts_text


async def run_daily_recap(
    now: datetime,
    fetch_rss_sources,  # async () -> list[SourceResult]
    fetch_x_sources,  # async () -> list[SourceResult]
    call_claude_extract,  # async (prompt: str) -> str (raw response text)
    call_claude_summarize,  # async (prompt: str) -> str
    push_facts_to_ha,  # async (facts: list[Fact]) -> list[PushResult]
    send_email,  # async (EmailContent) -> None
) -> EmailContent:
    try:
        rss_results = await fetch_rss_sources()
    except Exception:  # noqa: BLE001 - a fetch outage degrades to "found nothing", not a crash
        rss_results = []

    try:
        x_results = await fetch_x_sources()
    except Exception:  # noqa: BLE001
        x_results = []

    all_results: list[SourceResult] = rss_results + x_results
    posts = aggregate_sources(all_results)
    raw_feed_text = render_raw_feed_text(posts)
    missing = missing_sources(all_results)

    extraction_response = await call_claude_extract(build_extraction_prompt(raw_feed_text))
    facts = parse_extraction_response(extraction_response)

    push_results = await push_facts_to_ha(facts)

    facts_text = render_facts_text(facts)
    outline = await call_claude_summarize(build_summary_prompt(raw_feed_text, facts_text))

    day_number = compute_day_number(now.astimezone(ZoneInfo(BB28_TIMEZONE)).date())
    email_content = build_email_content(day_number, outline, push_results, missing)

    await send_email(email_content)
    return email_content
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: all tests across all 9 modules PASS

- [ ] **Step 6: Commit**

```bash
git add bb28_recap/pipeline.py tests/test_pipeline.py
git commit -m "feat: add pipeline orchestration - injected deps, source-fetch failure isolation"
git push
```

---

### Task 10: Vercel entry point, cron config, deploy

**Files:**
- Create: `api/daily-recap.py`
- Create: `vercel.json`
- Modify: `README.md` (already created in Task 1 — add the "how it actually runs" section below)

**No automated tests for this task** — this is the one place real clients (`twikit`, `anthropic`, `httpx`, `resend`) get constructed with real credentials; it cannot be tested without a real burner X account, real API keys, and a real reachable HA instance. Verify with `python -m py_compile api/daily-recap.py` plus a manual test run after deployment (Step 5 below).

**Before writing the `twikit` integration code:** `twikit`'s exact login/tweet-fetch API can drift between versions — verify the current API by checking twikit's PyPI page or GitHub README (`pip show twikit` after install, or fetch `https://pypi.org/project/twikit/` / `https://github.com/d60/twikit`) before finalizing the login/`get_user_tweets` calls below. The code in Step 1 reflects a commonly-documented `twikit` usage pattern (`Client().login(...)`, `get_user_by_screen_name`, `get_user_tweets(user_id, 'Tweets')`) but has not been verified against a live install in this environment — adjust the exact method names/arguments if the installed version differs, keeping the rest of this task's structure (the `TwikitXClient` wrapper implementing the `get_user_tweets(account) -> list[(text, datetime)]` shape Task 4 expects) unchanged.

- [ ] **Step 1: Write the Vercel entry point**

Create `api/daily-recap.py`:

```python
"""Vercel Cron entry point - the one place real clients get constructed.
No automated tests: verified by manual smoke test after deployment (see README)."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

import feedparser
import httpx
import resend
from anthropic import Anthropic
from twikit import Client as TwikitClient

from bb28_recap.config import (
    RECIPIENT_EMAIL,
    RSS_FEEDS,
    X_ACCOUNTS,
    load_env_config,
)
from bb28_recap.extract import EXTRACTION_SYSTEM_PROMPT
from bb28_recap.ha_push import build_ha_service_calls, push_service_calls
from bb28_recap.models import SourceResult
from bb28_recap.pipeline import run_daily_recap
from bb28_recap.sources_rss import fetch_rss_source
from bb28_recap.sources_x import fetch_x_source
from bb28_recap.summarize import SUMMARY_SYSTEM_PROMPT


class TwikitXClient:
    """Wraps twikit.Client into the get_user_tweets(account) -> list[(text, datetime)]
    shape bb28_recap.sources_x.fetch_x_source expects. Verify method names against
    the installed twikit version before relying on this in production - see the
    task note above."""

    def __init__(self, username: str, email: str, password: str) -> None:
        self._client = TwikitClient("en-US")
        self._username = username
        self._email = email
        self._password = password
        self._logged_in = False

    async def _ensure_login(self) -> None:
        if not self._logged_in:
            await self._client.login(
                auth_info_1=self._username,
                auth_info_2=self._email,
                password=self._password,
            )
            self._logged_in = True

    async def get_user_tweets(self, account: str) -> list[tuple[str, datetime]]:
        await self._ensure_login()
        user = await self._client.get_user_by_screen_name(account)
        tweets = await self._client.get_user_tweets(user.id, "Tweets")
        return [(t.text, t.created_at_datetime) for t in tweets]


async def _fetch_all_rss(now: datetime) -> list[SourceResult]:
    results = []
    for feed_url in RSS_FEEDS:
        results.append(fetch_rss_source(feed_url, now))
    return results


async def _fetch_all_x(client: TwikitXClient, now: datetime) -> list[SourceResult]:
    results = []
    for account in X_ACCOUNTS:
        results.append(await fetch_x_source(client, account, now))
    return results


async def _run(env: dict) -> None:
    config = load_env_config(env)
    now = datetime.now(timezone.utc)

    x_client = TwikitXClient(
        config["X_BURNER_USERNAME"], config["X_BURNER_EMAIL"], config["X_BURNER_PASSWORD"]
    )
    anthropic_client = Anthropic(api_key=config["ANTHROPIC_API_KEY"])
    resend.api_key = config["RESEND_API_KEY"]

    async def fetch_rss_sources():
        return await _fetch_all_rss(now)

    async def fetch_x_sources():
        return await _fetch_all_x(x_client, now)

    async def call_claude_extract(prompt: str) -> str:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def call_claude_summarize(prompt: str) -> str:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8192,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def push_facts_to_ha(facts):
        calls = build_ha_service_calls(facts)
        async with httpx.AsyncClient() as session:
            return await push_service_calls(
                session, config["HA_BASE_URL"], config["HA_LONG_LIVED_TOKEN"], calls
            )

    async def send_email(content):
        resend.Emails.send(
            {
                "from": "BB28 Daily Recap <onboarding@resend.dev>",
                "to": [RECIPIENT_EMAIL],
                "subject": content.subject,
                "text": content.body,
            }
        )

    await run_daily_recap(
        now,
        fetch_rss_sources,
        fetch_x_sources,
        call_claude_extract,
        call_claude_summarize,
        push_facts_to_ha,
        send_email,
    )


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            asyncio.run(_run(dict(os.environ)))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as exc:  # noqa: BLE001 - surface the error in the response + logs
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode())
            raise
```

- [ ] **Step 2: Create the cron config**

Create `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/daily-recap",
      "schedule": "0 22 * * *"
    }
  ]
}
```

- [ ] **Step 3: Compile-check**

Run: `python -m py_compile api/daily-recap.py bb28_recap/*.py`
Expected: no output, exit code 0 (install missing packages first: `pip install -r requirements.txt`)

- [ ] **Step 4: Run the full test suite one more time**

Run: `python -m pytest tests/ -v`
Expected: all tests still PASS (this task adds no new tests, just glue — confirms nothing else broke)

- [ ] **Step 5: Add the operational section to README.md**

Append to `README.md` (after the existing "Tests" section):

```markdown
## Manual smoke test (run this after deploying with real secrets)

There is no automated test for `api/daily-recap.py` - it's the one place
real credentials and network calls happen. After deploying to Vercel with
all 7 env vars set:

1. Trigger the function manually: visit `https://<your-deployment>.vercel.app/api/daily-recap`
   in a browser, or `curl` it.
2. Check it returns `200 OK`.
3. Check `info@jwsoat.com` received an email within a minute or two.
4. Check the email's "Auto-updated" section against your actual HA sensors
   (Settings -> Devices & Services -> Big Brother 28) to confirm the push
   actually landed.
5. Check Vercel's function logs (Vercel dashboard -> your project -> Logs)
   for any warnings about missing sources or failed HA pushes.
6. If `twikit`'s login/tweet-fetch API doesn't match what's implemented in
   `api/daily-recap.py` (see the note in `TwikitXClient`), the logs will
   show the exact error - adjust the method calls there without touching
   any file under `bb28_recap/` (that's all covered by pytest already).
```

- [ ] **Step 6: Commit, push, tag release**

```bash
git add api/daily-recap.py vercel.json README.md
git commit -m "feat: add Vercel entry point wiring real clients, cron config, smoke-test docs"
git push
gh release create v1.0.0 --title "v1.0.0" --notes "Initial release: scrapes 7 X accounts + 3 RSS feeds daily, extracts confirmed BB28 facts with Claude, pushes them into the big_brother_28 HA integration, and emails a 60+min talking-points outline. Requires 7 env vars set in Vercel before first real run (see README)."
```

