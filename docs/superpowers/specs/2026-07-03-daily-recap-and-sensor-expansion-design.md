# BB28 Daily Recap + Sensor Expansion — Design

## Goal

Give the user enough material every day to talk for 60+ minutes on a live podcast-style stream about Big Brother 28, delivered as an email before stream time, and expand the existing `big_brother_28` HA integration so the game-state sensors can be driven automatically instead of purely by hand.

Two components:

1. **HA integration changes** (existing repo `jwsoat/big-brother-28-ha`) — new statuses, auto-advancing event cycle, new aggregate sensors.
2. **New standalone project** (`bb28-daily-recap`, new public repo + Vercel Cron) — scrapes X, summarizes with Claude, emails a talking-points outline, and pushes structured updates into the HA sensors.

The two are decoupled: the HA integration works standalone (as it does today, via manual service calls); the Vercel project is an optional automated feeder that calls the same HA services a human would.

## 1. HA Integration Changes

### Housemate statuses

`HOUSEMATE_STATUSES` becomes:

```
HOH, Nominated, Veto Competitor, Veto Player, Safe, Eliminated
```

- `Veto Player` = current POV holder/winner (existing meaning, unchanged).
- `Veto Competitor` = new. Only applies to housemates playing in that week's veto competition who are **not** already HOH or Nominated (those two already imply participation, so they keep their existing status rather than being overwritten).

### Extra per-housemate attributes (not statuses — coexist with the main status)

- `have_not: bool` — food/lifestyle restriction, independent of game status. Toggled via new service `big_brother_28.set_have_not` (`name`, `is_have_not`).
- `jury_member: bool` — only meaningful once a housemate is `Eliminated`; distinguishes jury-phase boots from pre-jury boots. Toggled via new service `big_brother_28.set_jury_status` (`name`, `is_jury_member`).

### Event cycle (`next_event` auto-advance)

`EVENT_STATES` gains `"Veto Picks"`. The five cycle stages, in order:

```
HOH -> Nominations -> Veto Picks -> Veto -> Live Show -> (back to HOH)
```

`next_event` auto-advances whenever `set_housemate_status` produces one of these triggers (no separate service call needed for these transitions):

| Trigger | `next_event` becomes |
|---|---|
| A housemate's status is set to `HOH` | Nominations |
| 2+ housemates are currently `Nominated` (after this call) | Veto Picks |
| A non-HOH/non-nominee housemate's status is set to `Veto Competitor` | Veto |
| A housemate's status is set to `Veto Player` | Live Show |
| A housemate's status is set to `Eliminated` | HOH |

The existing `big_brother_28.set_next_event` service remains as a manual override (e.g. special episodes, double evictions) and always wins over the auto-advance for that call.

### New sensors

All computed from existing housemate entity state; each recomputes and calls `async_write_ha_state()` whenever a relevant housemate status/attribute changes (triggered from within the service handlers, not polling):

- `sensor.current_hoh` — name of whichever housemate has status `HOH`, or `"None"`.
- `sensor.current_have_nots` — comma-joined names of housemates with `have_not=True`, or `"None"`.
- `sensor.current_nominees` — comma-joined names of housemates with status `Nominated`.
- `sensor.current_veto_competitors` — comma-joined names of housemates with status `Veto Competitor` (does not include the HOH/nominees who are also playing but keep their own status).
- `sensor.jury_members` — comma-joined names of housemates with status `Eliminated` and `jury_member=True`.
- `sensor.week_number` — integer counter, `RestoreEntity`, starts at 1, increments by 1 each time the auto-advance cycle fires the `Eliminated -> HOH` transition (i.e. each week closes with an eviction).

## 2. New Project: `bb28-daily-recap`

New public GitHub repo, deployed as a Vercel Cron function (Python runtime). Fully decoupled from the HA integration's runtime — talks to it only over HTTP.

### Schedule

Vercel Cron, `0 22 * * *` (22:00 UTC = 3pm PT). BB28's season runs entirely within PDT, so no DST-boundary handling needed for this hardcoded offset.

### Sources

Seven X (Twitter) accounts, scraped daily for each account's last-24h posts:

```
TheBigBroTea, hamsterwatch, 89razorskate20, BBFeedsFairy, rbbq, bigbrothernet, BBigBrotherBuzz
```

### Auth

X requires an authenticated session for reliable access in 2026 — a dedicated burner X account (not the user's real account) logs in via `twikit`. Credentials stored as Vercel env secrets, never committed.

### Pipeline

1. **Scrape**: log in as the burner account, pull last-24h posts from all 7 accounts.
2. **Aggregate**: merge into one raw timestamped feed for the day, tagged by source account.
3. **Extract** (Claude call #1): given the raw feed, produce structured JSON of only clearly-stated facts (who won HOH, who's nominated, who's playing/won veto, who got evicted, have-not results) — each fact tagged with which account(s) stated it. Ambiguous/speculative chatter produces no fact.
4. **Push to HA**: for each extracted fact, call the matching HA service over REST (`POST {HA_BASE_URL}/api/services/big_brother_28/<service>`, authenticated with a long-lived access token) — `set_housemate_status`, `set_have_not`, `set_jury_status`, or `set_next_event` as an override where relevant. Failures (network/auth) are logged and skipped; they never block steps 5–6.
5. **Summarize** (Claude call #2): given the same raw feed (plus the facts extracted in step 3 for consistency), produce a segmented talking-points outline sized for 60+ minutes of live commentary: Overnight Recap, HOH/Nominations, Veto, Showmances, House Drama, Predictions/Wrap-up. Talking points, not a word-for-word script.
6. **Email**: send the outline via Resend to `info@jwsoat.com`, subject `BB28 Daily Recap — Day N` (day number computed locally from the same `2026-07-09` start date, in `America/Los_Angeles`). The email also lists what got auto-applied to HA in step 4 (e.g. "Auto-updated: Alex → Eliminated, per @hamsterwatch") so the user can visually confirm or correct via the existing HA services if a fact was wrong.

### Error handling

- A source account returning no new posts is called out in the email ("no fresh posts found for @X — possible scrape break"), not silently dropped.
- Claude/Resend/HA-push failures are logged to Vercel's function logs. No secondary delivery channel for v1 — a missing email is the signal something broke.

### Secrets (Vercel env vars)

`X_BURNER_USERNAME`, `X_BURNER_PASSWORD`, `X_BURNER_EMAIL`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `HA_BASE_URL`, `HA_LONG_LIVED_TOKEN`.

## Implementation order

The Vercel project's HA-push step depends on the new services (`set_have_not`, `set_jury_status`) and statuses (`Veto Competitor`) existing first. Build and ship the HA integration changes (section 1) before starting the Vercel project (section 2).

## Out of scope (for this spec)

- Full jury-vote modeling beyond the `jury_member` flag.
- Any data source besides the 7 named X accounts (no Facebook sources were ultimately provided).
- Retry/secondary delivery if the daily email fails to send.
- Historical archive/searchable log of past daily recaps.

## Risks

- **X scraping fragility**: burner-account session scraping can break if X changes auth flow or flags the account. Mitigated by the "flag missing source in email" behavior rather than silent gaps, but no auto-recovery in v1.
- **LLM extraction accuracy**: Claude misreading a joke/sarcastic post as a real game event would push a wrong status to HA. Mitigated by requiring clearly-stated facts only and surfacing every auto-applied change in the email for manual review/correction.
