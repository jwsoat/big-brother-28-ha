# BB28 HA Sensor Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `Veto Competitor` status, rename `Veto Player` to `Veto Winner`, add have-not/jury tracking, auto-advance the `next_event` sensor through the weekly HOH→Nominations→Veto Picks→Veto→Live Show cycle, and add six new aggregate sensors (`current_hoh`, `current_have_nots`, `current_nominees`, `current_veto_competitors`, `jury_members`, `week_number`) — all in the existing `custom_components/big_brother_28` integration.

**Architecture:** Business logic (aggregate computation + cycle-advance rules) lives in a new pure-Python module `logic.py` with zero Home Assistant imports, so it's unit-testable with plain `pytest` — no `pytest-homeassistant-custom-component` / real `homeassistant` install needed. `sensor.py` and `__init__.py` stay thin glue that calls into `logic.py` and writes entity state; this glue is verified by `python -m py_compile` plus a manual smoke-test checklist at the end, matching how the rest of this integration has been verified so far (there is no existing HA test harness in this repo).

**Tech Stack:** Python, Home Assistant custom component conventions (already established in this repo), `pytest` for the new `logic.py` unit tests.

## Global Constraints

- This is **Plan 1 of 2** per the spec's "Implementation order" section (`docs/superpowers/specs/2026-07-03-daily-recap-and-sensor-expansion-design.md`) — the separate `bb28-daily-recap` Vercel project depends on the services this plan adds and must not start before this plan ships.
- Status is `Veto Winner`, not `Veto Player` (renamed per spec revision).
- `Veto Competitor` only applies to non-HOH/non-nominee housemates drawn to play veto.
- Repo currently has zero automated tests — `tests/conftest.py` created in Task 1 is new test infrastructure, not a modification.
- After each task, run `python -m py_compile custom_components/big_brother_28/*.py` from the repo root to confirm the whole package still parses.

---

### Task 1: Update constants + stand up the pure-logic test harness

**Files:**
- Modify: `custom_components/big_brother_28/const.py`
- Create: `tests/conftest.py`
- Create: `tests/test_const.py`

**Interfaces:**
- Produces: `const.STATUS_VETO_COMPETITOR = "Veto Competitor"`, `const.STATUS_VETO_WINNER = "Veto Winner"` (replaces `STATUS_VETO_PLAYER`), `const.EVENT_VETO_PICKS = "Veto Picks"`, `const.ATTR_IS_HAVE_NOT = "is_have_not"`, `const.ATTR_IS_JURY_MEMBER = "is_jury_member"`, `const.SERVICE_SET_HAVE_NOT = "set_have_not"`, `const.SERVICE_SET_JURY_STATUS = "set_jury_status"`.
- Produces: `tests/conftest.py` registers `custom_components.big_brother_28.const` and `.logic` in `sys.modules` via direct file load, bypassing the package's real `__init__.py` (which imports `homeassistant` — not installed here). Every later test file can do a plain `from custom_components.big_brother_28 import const` / `import logic` and it resolves from this cache.

- [ ] **Step 1: Write the failing test**

Create `tests/test_const.py`:

```python
"""Sanity checks for the updated status/event constant lists."""
from custom_components.big_brother_28 import const


def test_veto_competitor_and_veto_winner_are_distinct_statuses():
    assert const.STATUS_VETO_COMPETITOR == "Veto Competitor"
    assert const.STATUS_VETO_WINNER == "Veto Winner"
    assert const.STATUS_VETO_COMPETITOR in const.HOUSEMATE_STATUSES
    assert const.STATUS_VETO_WINNER in const.HOUSEMATE_STATUSES


def test_veto_picks_event_state_exists():
    assert const.EVENT_VETO_PICKS == "Veto Picks"
    assert const.EVENT_VETO_PICKS in const.EVENT_STATES


def test_have_not_and_jury_attrs_exist():
    assert const.ATTR_IS_HAVE_NOT == "is_have_not"
    assert const.ATTR_IS_JURY_MEMBER == "is_jury_member"


def test_have_not_and_jury_services_exist():
    assert const.SERVICE_SET_HAVE_NOT == "set_have_not"
    assert const.SERVICE_SET_JURY_STATUS == "set_jury_status"
```

- [ ] **Step 2: Create the test harness so the test can even import the package**

Create `tests/conftest.py`:

```python
"""Load const.py/logic.py directly, without importing homeassistant.

The real custom_components/big_brother_28/__init__.py imports `homeassistant`,
which isn't installed in this test environment. Registering fake modules in
sys.modules *before* any test imports `custom_components.big_brother_28.*`
means Python's import system finds these cached stand-ins instead of
executing the real __init__.py.
"""
import importlib.util
import pathlib
import sys
import types

COMPONENT_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "big_brother_28"
)


def _register_stub_package() -> None:
    if "custom_components" not in sys.modules:
        pkg = types.ModuleType("custom_components")
        pkg.__path__ = []
        sys.modules["custom_components"] = pkg

    if "custom_components.big_brother_28" not in sys.modules:
        pkg = types.ModuleType("custom_components.big_brother_28")
        pkg.__path__ = [str(COMPONENT_DIR)]
        sys.modules["custom_components.big_brother_28"] = pkg


def _load_module(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, COMPONENT_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_register_stub_package()
_load_module("custom_components.big_brother_28.const", "const.py")
_load_module("custom_components.big_brother_28.logic", "logic.py")
```

Note: `logic.py` doesn't exist yet (Task 2 creates it) — `_load_module` for it will raise `FileNotFoundError` until then. That's expected for this task; Step 3 below only runs `test_const.py`, which doesn't need `logic.py` to be loadable... but `conftest.py` loads both eagerly on collection. To keep Task 1 self-contained, temporarily guard the logic.py load:

Replace the last line with:

```python
_load_module("custom_components.big_brother_28.const", "const.py")
if (COMPONENT_DIR / "logic.py").exists():
    _load_module("custom_components.big_brother_28.logic", "logic.py")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_const.py -v` (install pytest first if needed: `pip install pytest`)
Expected: FAIL — `AttributeError: module 'custom_components.big_brother_28.const' has no attribute 'STATUS_VETO_COMPETITOR'`

- [ ] **Step 4: Update const.py**

Replace the full contents of `custom_components/big_brother_28/const.py`:

```python
"""Constants for Big Brother 28 integration."""

DOMAIN = "big_brother_28"

CONF_START_DATE = "start_date"
CONF_HOUSEMATES = "housemates"
CONF_TIMEZONE = "timezone"

DEFAULT_START_DATE = "2026-07-09"
DEFAULT_TIMEZONE = "America/Los_Angeles"

STORAGE_VERSION = 1
STORAGE_KEY_HOUSEMATES = "housemates"

# Housemate statuses
STATUS_HOH = "HOH"
STATUS_NOMINATED = "Nominated"
STATUS_VETO_COMPETITOR = "Veto Competitor"
STATUS_VETO_WINNER = "Veto Winner"
STATUS_SAFE = "Safe"
STATUS_ELIMINATED = "Eliminated"

HOUSEMATE_STATUSES = [
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_COMPETITOR,
    STATUS_VETO_WINNER,
    STATUS_SAFE,
    STATUS_ELIMINATED,
]

DEFAULT_HOUSEMATE_STATUS = STATUS_SAFE

# Next-event states, in cycle order
EVENT_HOH = "HOH"
EVENT_NOMINATIONS = "Nominations"
EVENT_VETO_PICKS = "Veto Picks"
EVENT_VETO = "Veto"
EVENT_LIVE_SHOW = "Live Show"
EVENT_EVICTION = "Eviction"
EVENT_OTHER = "Other"

EVENT_STATES = [
    EVENT_HOH,
    EVENT_NOMINATIONS,
    EVENT_VETO_PICKS,
    EVENT_VETO,
    EVENT_LIVE_SHOW,
    EVENT_EVICTION,
    EVENT_OTHER,
]

DEFAULT_EVENT_STATE = EVENT_OTHER

SERVICE_ADD_HOUSEMATE = "add_housemate"
SERVICE_REMOVE_HOUSEMATE = "remove_housemate"
SERVICE_SET_HOUSEMATE_STATUS = "set_housemate_status"
SERVICE_SET_NEXT_EVENT = "set_next_event"
SERVICE_SET_HAVE_NOT = "set_have_not"
SERVICE_SET_JURY_STATUS = "set_jury_status"

ATTR_NAME = "name"
ATTR_STATUS = "status"
ATTR_EVENT_TYPE = "event_type"
ATTR_DETAIL = "detail"
ATTR_SCHEDULED_TIME = "scheduled_time"
ATTR_IS_HAVE_NOT = "is_have_not"
ATTR_IS_JURY_MEMBER = "is_jury_member"

SIGNAL_HOUSEMATES_UPDATED = f"{DOMAIN}_housemates_updated"

ICON_STATIC_URL = "/big_brother_28/icons/logo.jpg"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_const.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Compile-check the whole package**

Run: `python -m py_compile custom_components/big_brother_28/*.py`
Expected: no output, exit code 0. (`__init__.py` and `services.yaml` still reference `STATUS_VETO_PLAYER`/old event list at this point — that's fine, they're updated in later tasks. `sensor.py` and `__init__.py` don't reference the renamed constant directly by name today, so this still compiles.)

- [ ] **Step 7: Commit**

```bash
git add custom_components/big_brother_28/const.py tests/conftest.py tests/test_const.py
git commit -m "feat: rename Veto Player to Veto Winner, add Veto Competitor + have-not/jury constants"
```

---

### Task 2: `logic.py` — aggregate computation functions

**Files:**
- Create: `custom_components/big_brother_28/logic.py`
- Modify: `tests/conftest.py` (remove the `if exists()` guard now that `logic.py` will exist)
- Create: `tests/test_logic.py`

**Interfaces:**
- Consumes: `const.STATUS_HOH`, `const.STATUS_NOMINATED`, `const.STATUS_VETO_COMPETITOR`, `const.STATUS_ELIMINATED` (from Task 1).
- Produces: `logic.join_names_or_none(names: list[str]) -> str`, `logic.compute_current_hoh(statuses: dict[str, str]) -> str`, `logic.compute_nominees(statuses: dict[str, str]) -> list[str]`, `logic.compute_veto_competitors(statuses: dict[str, str]) -> list[str]`, `logic.compute_have_nots(have_not_flags: dict[str, bool]) -> list[str]`, `logic.compute_jury_members(statuses: dict[str, str], jury_flags: dict[str, bool]) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_logic.py`:

```python
"""Unit tests for pure BB28 game-state logic (no Home Assistant dependency)."""
from custom_components.big_brother_28 import logic
from custom_components.big_brother_28.const import (
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_SAFE,
    STATUS_VETO_COMPETITOR,
)


def test_join_names_or_none_empty():
    assert logic.join_names_or_none([]) == "None"


def test_join_names_or_none_joins_with_comma():
    assert logic.join_names_or_none(["Alex", "Jordan"]) == "Alex, Jordan"


def test_compute_current_hoh_finds_the_hoh():
    statuses = {"Alex": STATUS_HOH, "Jordan": STATUS_SAFE}
    assert logic.compute_current_hoh(statuses) == "Alex"


def test_compute_current_hoh_returns_none_string_when_no_hoh():
    statuses = {"Alex": STATUS_SAFE, "Jordan": STATUS_SAFE}
    assert logic.compute_current_hoh(statuses) == "None"


def test_compute_nominees_returns_all_nominated():
    statuses = {
        "Alex": STATUS_NOMINATED,
        "Jordan": STATUS_NOMINATED,
        "Sam": STATUS_SAFE,
    }
    assert sorted(logic.compute_nominees(statuses)) == ["Alex", "Jordan"]


def test_compute_veto_competitors_returns_only_that_status():
    statuses = {
        "Alex": STATUS_VETO_COMPETITOR,
        "Jordan": STATUS_HOH,
        "Sam": STATUS_SAFE,
    }
    assert logic.compute_veto_competitors(statuses) == ["Alex"]


def test_compute_have_nots_returns_flagged_names():
    flags = {"Alex": True, "Jordan": False, "Sam": True}
    assert sorted(logic.compute_have_nots(flags)) == ["Alex", "Sam"]


def test_compute_jury_members_requires_eliminated_and_flag():
    statuses = {
        "Alex": STATUS_ELIMINATED,
        "Jordan": STATUS_ELIMINATED,
        "Sam": STATUS_SAFE,
    }
    jury_flags = {"Alex": True, "Jordan": False, "Sam": True}
    assert logic.compute_jury_members(statuses, jury_flags) == ["Alex"]
```

Update `tests/conftest.py`'s last two lines back to unconditional (remove the `if exists()` guard added in Task 1):

```python
_load_module("custom_components.big_brother_28.const", "const.py")
_load_module("custom_components.big_brother_28.logic", "logic.py")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_logic.py -v`
Expected: FAIL — `FileNotFoundError` from `conftest.py`'s `_load_module` (no `logic.py` yet)

- [ ] **Step 3: Write the implementation**

Create `custom_components/big_brother_28/logic.py`:

```python
"""Pure, Home-Assistant-independent game-state logic for Big Brother 28."""
from __future__ import annotations

from .const import (
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_COMPETITOR,
)


def join_names_or_none(names: list[str]) -> str:
    return ", ".join(names) if names else "None"


def compute_current_hoh(statuses: dict[str, str]) -> str:
    for name, status in statuses.items():
        if status == STATUS_HOH:
            return name
    return "None"


def compute_nominees(statuses: dict[str, str]) -> list[str]:
    return [name for name, status in statuses.items() if status == STATUS_NOMINATED]


def compute_veto_competitors(statuses: dict[str, str]) -> list[str]:
    return [
        name
        for name, status in statuses.items()
        if status == STATUS_VETO_COMPETITOR
    ]


def compute_have_nots(have_not_flags: dict[str, bool]) -> list[str]:
    return [name for name, is_have_not in have_not_flags.items() if is_have_not]


def compute_jury_members(
    statuses: dict[str, str], jury_flags: dict[str, bool]
) -> list[str]:
    return [
        name
        for name, status in statuses.items()
        if status == STATUS_ELIMINATED and jury_flags.get(name, False)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_logic.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Compile-check the whole package**

Run: `python -m py_compile custom_components/big_brother_28/*.py`
Expected: no output, exit code 0

- [ ] **Step 6: Commit**

```bash
git add custom_components/big_brother_28/logic.py tests/conftest.py tests/test_logic.py
git commit -m "feat: add pure aggregate-computation logic for current_hoh/nominees/veto/have-nots/jury"
```

---

### Task 3: `logic.py` — event cycle auto-advance

**Files:**
- Modify: `custom_components/big_brother_28/logic.py`
- Modify: `tests/test_logic.py`

**Interfaces:**
- Consumes: `const.STATUS_HOH`, `const.STATUS_NOMINATED`, `const.STATUS_VETO_COMPETITOR`, `const.STATUS_VETO_WINNER`, `const.STATUS_ELIMINATED`, `const.EVENT_HOH`, `const.EVENT_NOMINATIONS`, `const.EVENT_VETO_PICKS`, `const.EVENT_VETO`, `const.EVENT_LIVE_SHOW`; `logic.compute_nominees` (from Task 2).
- Produces: `logic.next_event_after_status_change(new_status: str, statuses_after_change: dict[str, str]) -> str | None`, `logic.is_week_advancing_status(new_status: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_logic.py`:

```python
from custom_components.big_brother_28.const import (
    EVENT_HOH,
    EVENT_LIVE_SHOW,
    EVENT_NOMINATIONS,
    EVENT_VETO,
    EVENT_VETO_PICKS,
    STATUS_VETO_WINNER,
)


def test_hoh_status_advances_to_nominations():
    result = logic.next_event_after_status_change(STATUS_HOH, {"Alex": STATUS_HOH})
    assert result == EVENT_NOMINATIONS


def test_single_nominee_does_not_advance_yet():
    statuses = {"Alex": STATUS_NOMINATED, "Jordan": STATUS_SAFE}
    assert logic.next_event_after_status_change(STATUS_NOMINATED, statuses) is None


def test_second_nominee_advances_to_veto_picks():
    statuses = {"Alex": STATUS_NOMINATED, "Jordan": STATUS_NOMINATED}
    result = logic.next_event_after_status_change(STATUS_NOMINATED, statuses)
    assert result == EVENT_VETO_PICKS


def test_veto_competitor_status_advances_to_veto():
    statuses = {"Alex": STATUS_VETO_COMPETITOR}
    result = logic.next_event_after_status_change(STATUS_VETO_COMPETITOR, statuses)
    assert result == EVENT_VETO


def test_veto_winner_status_advances_to_live_show():
    statuses = {"Alex": STATUS_VETO_WINNER}
    result = logic.next_event_after_status_change(STATUS_VETO_WINNER, statuses)
    assert result == EVENT_LIVE_SHOW


def test_eliminated_status_advances_to_hoh():
    statuses = {"Alex": STATUS_ELIMINATED}
    result = logic.next_event_after_status_change(STATUS_ELIMINATED, statuses)
    assert result == EVENT_HOH


def test_safe_status_does_not_advance():
    statuses = {"Alex": STATUS_SAFE}
    assert logic.next_event_after_status_change(STATUS_SAFE, statuses) is None


def test_eliminated_status_advances_the_week():
    assert logic.is_week_advancing_status(STATUS_ELIMINATED) is True


def test_hoh_status_does_not_advance_the_week():
    assert logic.is_week_advancing_status(STATUS_HOH) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_logic.py -v`
Expected: FAIL — `AttributeError: module 'custom_components.big_brother_28.logic' has no attribute 'next_event_after_status_change'`

- [ ] **Step 3: Write the implementation**

Append to `custom_components/big_brother_28/logic.py` (add these imports to the existing `from .const import (...)` block: `STATUS_VETO_WINNER`, `EVENT_HOH`, `EVENT_NOMINATIONS`, `EVENT_VETO_PICKS`, `EVENT_VETO`, `EVENT_LIVE_SHOW`):

```python
from .const import (
    EVENT_HOH,
    EVENT_LIVE_SHOW,
    EVENT_NOMINATIONS,
    EVENT_VETO,
    EVENT_VETO_PICKS,
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_COMPETITOR,
    STATUS_VETO_WINNER,
)
```

(this replaces the Task 2 import block at the top of the file)

Then add at the bottom of `logic.py`:

```python
def next_event_after_status_change(
    new_status: str, statuses_after_change: dict[str, str]
) -> str | None:
    """Return the next_event value triggered by this status change, or None."""
    if new_status == STATUS_HOH:
        return EVENT_NOMINATIONS
    if new_status == STATUS_NOMINATED:
        if len(compute_nominees(statuses_after_change)) >= 2:
            return EVENT_VETO_PICKS
        return None
    if new_status == STATUS_VETO_COMPETITOR:
        return EVENT_VETO
    if new_status == STATUS_VETO_WINNER:
        return EVENT_LIVE_SHOW
    if new_status == STATUS_ELIMINATED:
        return EVENT_HOH
    return None


def is_week_advancing_status(new_status: str) -> bool:
    """True if this status change closes out a BB week (eviction)."""
    return new_status == STATUS_ELIMINATED
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_logic.py -v`
Expected: PASS (17 tests total)

- [ ] **Step 5: Compile-check the whole package**

Run: `python -m py_compile custom_components/big_brother_28/*.py`
Expected: no output, exit code 0

- [ ] **Step 6: Commit**

```bash
git add custom_components/big_brother_28/logic.py tests/test_logic.py
git commit -m "feat: add event-cycle auto-advance logic (HOH->Nominations->Veto Picks->Veto->Live Show)"
```

---

### Task 4: Wire `logic.py` into `sensor.py` — new attributes + new aggregate sensors

**Files:**
- Modify: `custom_components/big_brother_28/sensor.py`

**Interfaces:**
- Consumes: everything from `logic.py` (Tasks 2–3) and the new `const.py` names (Task 1).
- Produces: `BB28HousemateSensor.have_not` (property, bool), `BB28HousemateSensor.jury_member` (property, bool), `BB28HousemateSensor.set_have_not(is_have_not: bool)`, `BB28HousemateSensor.set_jury_status(is_jury_member: bool)` — consumed by `__init__.py` in Task 5. New classes `BB28CurrentHOHSensor`, `BB28CurrentHaveNotsSensor`, `BB28CurrentNomineesSensor`, `BB28CurrentVetoCompetitorsSensor`, `BB28JuryMembersSensor`, `BB28WeekNumberSensor`, each with a `.refresh()` method (aggregates) or `.advance_week()` (week number) — consumed by `__init__.py` in Task 5. `hass.data[DOMAIN][entry.entry_id]["week_number_entity"]` and `["aggregate_entities"]` (list) — consumed by `__init__.py` in Task 5.

- [ ] **Step 1: Update imports**

In `custom_components/big_brother_28/sensor.py`, replace the `from .const import (...)` block with:

```python
from . import logic
from .const import (
    ATTR_IS_HAVE_NOT,
    ATTR_IS_JURY_MEMBER,
    CONF_HOUSEMATES,
    CONF_START_DATE,
    CONF_TIMEZONE,
    DEFAULT_EVENT_STATE,
    DEFAULT_HOUSEMATE_STATUS,
    DEFAULT_TIMEZONE,
    DOMAIN,
    ICON_STATIC_URL,
)
```

- [ ] **Step 2: Update `BB28HousemateSensor` with have-not/jury attributes**

Replace the `BB28HousemateSensor` class body (everything from `class BB28HousemateSensor` to the end of the file) with:

```python
class BB28HousemateSensor(RestoreEntity, SensorEntity):
    """Status of a single housemate."""

    _attr_icon = "mdi:account"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, name: str) -> None:
        self._entry = entry
        self._name_value = name
        slug = name.lower().replace(" ", "_")
        self._attr_unique_id = f"{entry.entry_id}_housemate_{slug}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)
        self._state = DEFAULT_HOUSEMATE_STATUS
        self._have_not = False
        self._jury_member = False

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def have_not(self) -> bool:
        return self._have_not

    @property
    def jury_member(self) -> bool:
        return self._jury_member

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "housemate": self._name_value,
            ATTR_IS_HAVE_NOT: self._have_not,
            ATTR_IS_JURY_MEMBER: self._jury_member,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            self._state = last_state.state
            self._have_not = bool(last_state.attributes.get(ATTR_IS_HAVE_NOT, False))
            self._jury_member = bool(
                last_state.attributes.get(ATTR_IS_JURY_MEMBER, False)
            )

    def set_status(self, status: str) -> None:
        self._state = status
        self.async_write_ha_state()

    def set_have_not(self, is_have_not: bool) -> None:
        self._have_not = is_have_not
        self.async_write_ha_state()

    def set_jury_status(self, is_jury_member: bool) -> None:
        self._jury_member = is_jury_member
        self.async_write_ha_state()


class BB28WeekNumberSensor(RestoreEntity, SensorEntity):
    """BB week counter - increments each time an eviction closes out a week."""

    _attr_icon = "mdi:calendar-week"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_week_number"
        self._attr_name = "Week Number"
        self._attr_device_info = _device_info(entry)
        self._week = 1

    @property
    def native_value(self) -> int:
        return self._week

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            try:
                self._week = int(last_state.state)
            except ValueError:
                pass

    def advance_week(self) -> None:
        self._week += 1
        self.async_write_ha_state()


class BB28CurrentHOHSensor(SensorEntity):
    """Aggregate: name of whoever currently holds HOH."""

    _attr_icon = "mdi:crown"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, housemate_entities: dict) -> None:
        self._entry = entry
        self._housemate_entities = housemate_entities
        self._attr_unique_id = f"{entry.entry_id}_current_hoh"
        self._attr_name = "Current HOH"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        statuses = {
            name: entity.native_value
            for name, entity in self._housemate_entities.items()
        }
        return logic.compute_current_hoh(statuses)

    def refresh(self) -> None:
        self.async_write_ha_state()


class BB28CurrentNomineesSensor(SensorEntity):
    """Aggregate: comma-joined list of currently nominated housemates."""

    _attr_icon = "mdi:target-account"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, housemate_entities: dict) -> None:
        self._entry = entry
        self._housemate_entities = housemate_entities
        self._attr_unique_id = f"{entry.entry_id}_current_nominees"
        self._attr_name = "Current Nominees"
        self._attr_device_info = _device_info(entry)

    @property
    def _names(self) -> list[str]:
        statuses = {
            name: entity.native_value
            for name, entity in self._housemate_entities.items()
        }
        return logic.compute_nominees(statuses)

    @property
    def native_value(self) -> str:
        return logic.join_names_or_none(self._names)

    @property
    def extra_state_attributes(self) -> dict:
        return {"names": self._names}

    def refresh(self) -> None:
        self.async_write_ha_state()


class BB28CurrentVetoCompetitorsSensor(SensorEntity):
    """Aggregate: comma-joined list of housemates playing in this week's veto."""

    _attr_icon = "mdi:shield-account"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, housemate_entities: dict) -> None:
        self._entry = entry
        self._housemate_entities = housemate_entities
        self._attr_unique_id = f"{entry.entry_id}_current_veto_competitors"
        self._attr_name = "Current Veto Competitors"
        self._attr_device_info = _device_info(entry)

    @property
    def _names(self) -> list[str]:
        statuses = {
            name: entity.native_value
            for name, entity in self._housemate_entities.items()
        }
        return logic.compute_veto_competitors(statuses)

    @property
    def native_value(self) -> str:
        return logic.join_names_or_none(self._names)

    @property
    def extra_state_attributes(self) -> dict:
        return {"names": self._names}

    def refresh(self) -> None:
        self.async_write_ha_state()


class BB28CurrentHaveNotsSensor(SensorEntity):
    """Aggregate: comma-joined list of housemates currently flagged have-not."""

    _attr_icon = "mdi:food-off"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, housemate_entities: dict) -> None:
        self._entry = entry
        self._housemate_entities = housemate_entities
        self._attr_unique_id = f"{entry.entry_id}_current_have_nots"
        self._attr_name = "Current Have-Nots"
        self._attr_device_info = _device_info(entry)

    @property
    def _names(self) -> list[str]:
        flags = {
            name: entity.have_not
            for name, entity in self._housemate_entities.items()
        }
        return logic.compute_have_nots(flags)

    @property
    def native_value(self) -> str:
        return logic.join_names_or_none(self._names)

    @property
    def extra_state_attributes(self) -> dict:
        return {"names": self._names}

    def refresh(self) -> None:
        self.async_write_ha_state()


class BB28JuryMembersSensor(SensorEntity):
    """Aggregate: comma-joined list of eliminated housemates on the jury."""

    _attr_icon = "mdi:gavel"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, housemate_entities: dict) -> None:
        self._entry = entry
        self._housemate_entities = housemate_entities
        self._attr_unique_id = f"{entry.entry_id}_jury_members"
        self._attr_name = "Jury Members"
        self._attr_device_info = _device_info(entry)

    @property
    def _names(self) -> list[str]:
        statuses = {
            name: entity.native_value
            for name, entity in self._housemate_entities.items()
        }
        jury_flags = {
            name: entity.jury_member
            for name, entity in self._housemate_entities.items()
        }
        return logic.compute_jury_members(statuses, jury_flags)

    @property
    def native_value(self) -> str:
        return logic.join_names_or_none(self._names)

    @property
    def extra_state_attributes(self) -> dict:
        return {"names": self._names}

    def refresh(self) -> None:
        self.async_write_ha_state()
```

- [ ] **Step 3: Update `async_setup_entry` to build and register the new sensors**

Replace the `async_setup_entry` function near the top of `sensor.py` with:

```python
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]

    house_day = BB28HouseDaySensor(entry)
    house_time = BB28HouseTimeSensor(entry)
    next_event = BB28NextEventSensor(entry)
    week_number = BB28WeekNumberSensor(entry)

    housemate_entities: dict[str, BB28HousemateSensor] = store["housemate_entities"]

    current_hoh = BB28CurrentHOHSensor(entry, housemate_entities)
    current_have_nots = BB28CurrentHaveNotsSensor(entry, housemate_entities)
    current_nominees = BB28CurrentNomineesSensor(entry, housemate_entities)
    current_veto_competitors = BB28CurrentVetoCompetitorsSensor(
        entry, housemate_entities
    )
    jury_members = BB28JuryMembersSensor(entry, housemate_entities)

    store["next_event_entity"] = next_event
    store["house_day_entity"] = house_day
    store["week_number_entity"] = week_number
    store["aggregate_entities"] = [
        current_hoh,
        current_have_nots,
        current_nominees,
        current_veto_competitors,
        jury_members,
    ]

    entities: list[SensorEntity] = [
        house_day,
        house_time,
        next_event,
        week_number,
        current_hoh,
        current_have_nots,
        current_nominees,
        current_veto_competitors,
        jury_members,
    ]

    for name in entry.options.get(CONF_HOUSEMATES, []):
        housemate = BB28HousemateSensor(entry, name)
        housemate_entities[name] = housemate
        entities.append(housemate)

    async_add_entities(entities)
```

- [ ] **Step 4: Compile-check**

Run: `python -m py_compile custom_components/big_brother_28/*.py`
Expected: no output, exit code 0

- [ ] **Step 5: Commit**

```bash
git add custom_components/big_brother_28/sensor.py
git commit -m "feat: add have-not/jury attrs and 6 new aggregate sensors to sensor.py"
```

---

### Task 5: Wire auto-advance + new services into `__init__.py`

**Files:**
- Modify: `custom_components/big_brother_28/__init__.py`

**Interfaces:**
- Consumes: `logic.next_event_after_status_change`, `logic.is_week_advancing_status` (Task 3); `BB28HousemateSensor.set_have_not`, `.set_jury_status` (Task 4); `store["week_number_entity"].advance_week()`, `store["aggregate_entities"]` list of entities each with `.refresh()` (Task 4); `const.SERVICE_SET_HAVE_NOT`, `const.SERVICE_SET_JURY_STATUS`, `const.ATTR_IS_HAVE_NOT`, `const.ATTR_IS_JURY_MEMBER` (Task 1).
- Produces: two new HA services `big_brother_28.set_have_not` and `big_brother_28.set_jury_status`; `set_housemate_status` now also auto-advances `next_event` and `week_number` per the cycle rules.

- [ ] **Step 1: Replace the full contents of `__init__.py`**

```python
"""Big Brother 28 integration."""
from __future__ import annotations

import os

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from . import logic
from .const import (
    ATTR_DETAIL,
    ATTR_EVENT_TYPE,
    ATTR_IS_HAVE_NOT,
    ATTR_IS_JURY_MEMBER,
    ATTR_NAME,
    ATTR_SCHEDULED_TIME,
    ATTR_STATUS,
    CONF_HOUSEMATES,
    CONF_START_DATE,
    DOMAIN,
    EVENT_STATES,
    HOUSEMATE_STATUSES,
    ICON_STATIC_URL,
    SERVICE_ADD_HOUSEMATE,
    SERVICE_REMOVE_HOUSEMATE,
    SERVICE_SET_HAVE_NOT,
    SERVICE_SET_HOUSEMATE_STATUS,
    SERVICE_SET_JURY_STATUS,
    SERVICE_SET_NEXT_EVENT,
)

PLATFORMS = ["sensor"]

ADD_HOUSEMATE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})
REMOVE_HOUSEMATE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})
SET_HOUSEMATE_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_STATUS): vol.In(HOUSEMATE_STATUSES),
    }
)
SET_NEXT_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EVENT_TYPE): vol.In(EVENT_STATES),
        vol.Optional(ATTR_DETAIL, default=""): cv.string,
        vol.Optional(ATTR_SCHEDULED_TIME): cv.string,
    }
)
SET_HAVE_NOT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_IS_HAVE_NOT): cv.boolean,
    }
)
SET_JURY_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_IS_JURY_MEMBER): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "housemate_entities": {},
        "next_event_entity": None,
        "house_day_entity": None,
        "week_number_entity": None,
        "aggregate_entities": [],
    }

    await _async_register_icon_path(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)

    return True


async def _async_register_icon_path(hass: HomeAssistant) -> None:
    if hass.data[DOMAIN].get("_icon_path_registered"):
        return
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/big_brother_28/icons", icons_dir, cache_headers=False)]
    )
    hass.data[DOMAIN]["_icon_path_registered"] = True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _refresh_aggregates(hass: HomeAssistant, entry_id: str) -> None:
    for entity in hass.data[DOMAIN][entry_id]["aggregate_entities"]:
        entity.refresh()


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ADD_HOUSEMATE):
        return

    async def _get_entry(call: ServiceCall) -> ConfigEntry:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ValueError("Big Brother 28 is not configured")
        return entries[0]

    async def add_housemate(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        name = call.data[ATTR_NAME].strip()
        housemates = list(entry.options.get(CONF_HOUSEMATES, []))
        if name not in housemates:
            housemates.append(name)
            hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_HOUSEMATES: housemates},
            )

    async def remove_housemate(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        name = call.data[ATTR_NAME].strip()
        housemates = [h for h in entry.options.get(CONF_HOUSEMATES, []) if h != name]
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_HOUSEMATES: housemates},
        )

    async def set_housemate_status(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        name = call.data[ATTR_NAME].strip()
        status = call.data[ATTR_STATUS]
        store = hass.data[DOMAIN][entry.entry_id]
        entities = store["housemate_entities"]
        entity = entities.get(name)
        if entity is None:
            raise ValueError(f"No housemate sensor found for '{name}'")

        entity.set_status(status)

        updated_statuses = {
            housemate_name: housemate_entity.native_value
            for housemate_name, housemate_entity in entities.items()
        }
        next_event_value = logic.next_event_after_status_change(
            status, updated_statuses
        )
        if next_event_value is not None:
            store["next_event_entity"].set_event(next_event_value)

        if logic.is_week_advancing_status(status):
            store["week_number_entity"].advance_week()

        _refresh_aggregates(hass, entry.entry_id)

    async def set_next_event(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        entity = hass.data[DOMAIN][entry.entry_id]["next_event_entity"]
        if entity is None:
            raise ValueError("Next event sensor not ready")
        entity.set_event(
            call.data[ATTR_EVENT_TYPE],
            call.data.get(ATTR_DETAIL, ""),
            call.data.get(ATTR_SCHEDULED_TIME),
        )

    async def set_have_not(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        name = call.data[ATTR_NAME].strip()
        is_have_not = call.data[ATTR_IS_HAVE_NOT]
        entities = hass.data[DOMAIN][entry.entry_id]["housemate_entities"]
        entity = entities.get(name)
        if entity is None:
            raise ValueError(f"No housemate sensor found for '{name}'")
        entity.set_have_not(is_have_not)
        _refresh_aggregates(hass, entry.entry_id)

    async def set_jury_status(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        name = call.data[ATTR_NAME].strip()
        is_jury_member = call.data[ATTR_IS_JURY_MEMBER]
        entities = hass.data[DOMAIN][entry.entry_id]["housemate_entities"]
        entity = entities.get(name)
        if entity is None:
            raise ValueError(f"No housemate sensor found for '{name}'")
        entity.set_jury_status(is_jury_member)
        _refresh_aggregates(hass, entry.entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_HOUSEMATE, add_housemate, schema=ADD_HOUSEMATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_HOUSEMATE,
        remove_housemate,
        schema=REMOVE_HOUSEMATE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOUSEMATE_STATUS,
        set_housemate_status,
        schema=SET_HOUSEMATE_STATUS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_NEXT_EVENT, set_next_event, schema=SET_NEXT_EVENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_HAVE_NOT, set_have_not, schema=SET_HAVE_NOT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_JURY_STATUS,
        set_jury_status,
        schema=SET_JURY_STATUS_SCHEMA,
    )
```

- [ ] **Step 2: Compile-check**

Run: `python -m py_compile custom_components/big_brother_28/*.py`
Expected: no output, exit code 0

- [ ] **Step 3: Commit**

```bash
git add custom_components/big_brother_28/__init__.py
git commit -m "feat: add set_have_not/set_jury_status services, auto-advance next_event + week_number"
```

---

### Task 6: Update `services.yaml`, bump manifest version, manual smoke test, release

**Files:**
- Modify: `custom_components/big_brother_28/services.yaml`
- Modify: `custom_components/big_brother_28/manifest.json`

- [ ] **Step 1: Replace `services.yaml`**

```yaml
add_housemate:
  name: Add housemate
  description: Add a housemate and create their status sensor.
  fields:
    name:
      required: true
      example: "Alex"
      selector:
        text:

remove_housemate:
  name: Remove housemate
  description: Remove a housemate's status sensor.
  fields:
    name:
      required: true
      example: "Alex"
      selector:
        text:

set_housemate_status:
  name: Set housemate status
  description: >-
    Update a housemate's current status. Also auto-advances the Next Event
    sensor per the weekly cycle (HOH -> Nominations -> Veto Picks -> Veto ->
    Live Show -> back to HOH).
  fields:
    name:
      required: true
      example: "Alex"
      selector:
        text:
    status:
      required: true
      selector:
        select:
          options:
            - "HOH"
            - "Nominated"
            - "Veto Competitor"
            - "Veto Winner"
            - "Safe"
            - "Eliminated"

set_next_event:
  name: Set next event
  description: Manually override the next upcoming event.
  fields:
    event_type:
      required: true
      selector:
        select:
          options:
            - "HOH"
            - "Nominations"
            - "Veto Picks"
            - "Veto"
            - "Live Show"
            - "Eviction"
            - "Other"
    detail:
      required: false
      example: "Veto Ceremony"
      selector:
        text:
    scheduled_time:
      required: false
      example: "2026-07-10T20:00:00"
      selector:
        datetime:

set_have_not:
  name: Set have-not status
  description: Toggle whether a housemate is currently a have-not.
  fields:
    name:
      required: true
      example: "Alex"
      selector:
        text:
    is_have_not:
      required: true
      selector:
        boolean:

set_jury_status:
  name: Set jury status
  description: Toggle whether an eliminated housemate is on the jury.
  fields:
    name:
      required: true
      example: "Alex"
      selector:
        text:
    is_jury_member:
      required: true
      selector:
        boolean:
```

- [ ] **Step 2: Bump `manifest.json` version**

In `custom_components/big_brother_28/manifest.json`, change:

```json
  "version": "1.1.0"
```

to:

```json
  "version": "1.2.0"
```

- [ ] **Step 3: Run the full test suite + compile check**

Run: `python -m pytest tests/ -v && python -m py_compile custom_components/big_brother_28/*.py`
Expected: all tests PASS, compile check silent/exit 0

- [ ] **Step 4: Validate `services.yaml`/`manifest.json` are well-formed**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('custom_components/big_brother_28/services.yaml'))"
python -c "import json; json.load(open('custom_components/big_brother_28/manifest.json'))"
```
Expected: no output, exit code 0 (install `pyyaml` first if missing: `pip install pyyaml`)

- [ ] **Step 5: Manual smoke test checklist (no automated HA test harness in this repo — verify by hand in a real HA instance)**

After installing this version in Home Assistant (HACS update or manual copy + restart):

- [ ] Add 3 test housemates via `big_brother_28.add_housemate`.
- [ ] Call `set_housemate_status` with `status: HOH` on one housemate → confirm `sensor.next_event` becomes `Nominations` and `sensor.current_hoh` shows that housemate's name.
- [ ] Call `set_housemate_status` with `status: Nominated` on one other housemate → confirm `next_event` is still `Nominations` (only 1 nominee so far) and `sensor.current_nominees` lists that one name.
- [ ] Call `set_housemate_status` with `status: Nominated` on a second housemate → confirm `next_event` becomes `Veto Picks` and `sensor.current_nominees` lists both names.
- [ ] Call `set_housemate_status` with `status: Veto Competitor` on the third (non-HOH/non-nominee) housemate → confirm `next_event` becomes `Veto` and `sensor.current_veto_competitors` shows that name.
- [ ] Call `set_housemate_status` with `status: Veto Winner` on any housemate → confirm `next_event` becomes `Live Show`.
- [ ] Call `set_housemate_status` with `status: Eliminated` on any housemate → confirm `next_event` becomes `HOH` and `sensor.week_number` increments from 1 to 2.
- [ ] Call `big_brother_28.set_have_not` with `is_have_not: true` on a housemate → confirm `sensor.current_have_nots` lists them and their own sensor's `is_have_not` attribute is `true`.
- [ ] Call `big_brother_28.set_jury_status` with `is_jury_member: true` on the eliminated housemate → confirm `sensor.jury_members` lists them.
- [ ] Restart Home Assistant → confirm `sensor.week_number`, all housemate statuses, and the have-not/jury attributes survive the restart (RestoreEntity working).
- [ ] Remove the 3 test housemates via `remove_housemate` once verified.

- [ ] **Step 6: Commit and tag release**

```bash
git add custom_components/big_brother_28/services.yaml custom_components/big_brother_28/manifest.json
git commit -m "chore: update services.yaml for new statuses/services, bump version to 1.2.0"
git push
gh release create v1.2.0 --title "v1.2.0" --notes "Veto Winner rename, Veto Competitor status, have-not/jury tracking, auto-advancing next_event cycle, 6 new aggregate sensors (current_hoh, current_have_nots, current_nominees, current_veto_competitors, jury_members, week_number)."
```
