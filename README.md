# Big Brother 28 — Home Assistant Integration

Track HOH, nominations, veto, evictions, and house day/time for Big Brother 28 in Home Assistant.

## Install (HACS)

1. HACS → ⋮ menu → Custom repositories → add `https://github.com/jwsoat/big-brother-28-ha`, category **Integration**.
2. Install "Big Brother 28", restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **Big Brother 28**.
4. Confirm the season start date (defaults 2026-07-09) and house timezone (defaults `America/Los_Angeles` — the show runs on PT regardless of your HA server's own timezone).

Housemates aren't known until the cast reveal — add them live once announced, no reinstall or restart needed.

Both start date and timezone are editable later via the integration's **Configure** button.

## Entities

| Entity | States |
|---|---|
| `sensor.house_day` | Day N, auto-computed from start date at PT midnight |
| `sensor.house_time` | live clock, HH:MM, in house timezone |
| `sensor.next_event` | HOH / Nominations / Veto Picks / Veto / Live Show / Eviction / Other (+ `detail`, `scheduled_time` attrs) |
| `sensor.<housemate_name>` | HOH / Nominated / Veto Competitor / Veto Winner / Safe / Eliminated / Jury |
| `sensor.week_number` | Current BB week number, increments each eviction |
| `sensor.current_hoh` | Name of whoever currently holds HOH |
| `sensor.current_nominees` | Comma-joined list of currently nominated housemates |
| `sensor.current_veto_competitors` | Comma-joined list of housemates playing in this week's veto |
| `sensor.current_have_nots` | Comma-joined list of housemates currently flagged have-not |
| `sensor.jury_members` | Comma-joined list of eliminated housemates on the jury |

`next_event` auto-advances through the weekly cycle (HOH → Nominations → Veto Picks → Veto → Live Show → back to HOH on eviction) whenever a housemate's status is set to HOH, their 2nd Nominated, Veto Competitor, Veto Winner, or Eliminated — you don't need a separate `set_next_event` call for those transitions. Use `set_next_event` only for manual overrides (e.g. scheduling Live Show or Eviction times).

## Services

```yaml
service: big_brother_28.add_housemate
data: { name: "Alex" }

service: big_brother_28.set_housemate_status
data: { name: "Alex", status: "HOH" }  # also accepts: Nominated, Veto Competitor, Veto Winner, Safe, Eliminated, Jury
# set_housemate_status / set_have_not auto-create the housemate sensor if
# `name` isn't known yet — no separate add_housemate call needed for
# automations that only learn a name from a live-feed fact.

service: big_brother_28.set_next_event
data: { event_type: "Veto", detail: "Veto Ceremony", scheduled_time: "2026-07-10T20:00:00" }

service: big_brother_28.set_have_not
data: { name: "Alex", is_have_not: true }

service: big_brother_28.remove_housemate
data: { name: "Alex" }
```
