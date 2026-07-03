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
| `sensor.next_event` | HOH / Veto / Live Show / Eviction / Nominations / Other (+ `detail`, `scheduled_time` attrs) |
| `sensor.<housemate_name>` | HOH / Nominated / Veto Player / Safe / Eliminated |

## Services

```yaml
service: big_brother_28.add_housemate
data: { name: "Alex" }

service: big_brother_28.set_housemate_status
data: { name: "Alex", status: "HOH" }

service: big_brother_28.set_next_event
data: { event_type: "Veto", detail: "Veto Ceremony", scheduled_time: "2026-07-10T20:00:00" }

service: big_brother_28.remove_housemate
data: { name: "Alex" }
```
