"""Mode contract — single source of truth for all mode behavior.

Each mode is a frozen data object. UI, overlays, and strategy logic
read from these descriptors instead of scattering conditionals.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TabDef:
    """One tab in the strategy page."""
    id: str
    label: str


@dataclass(frozen=True)
class ModeDescriptor:
    """Complete behavioral contract for one mode."""
    key: str
    display_name: str
    overlay_profile: frozenset[str]
    default_tab: str
    available_tabs: tuple[TabDef, ...]
    auto_record_practice: bool
    alert_policy: str  # "critical_only" | "all" | "none"
    sync_tags: tuple[str, ...]

    def tab_ids(self) -> list[str]:
        return [t.id for t in self.available_tabs]

    def tab_dicts(self) -> list[dict[str, str]]:
        return [{"id": t.id, "label": t.label} for t in self.available_tabs]

    def has_tab(self, tab_id: str) -> bool:
        return any(t.id == tab_id for t in self.available_tabs)

    def resolve_active_tab(self, has_plan: bool, has_profiles: bool) -> str:
        """Return the best default tab given current state."""
        if self.key == "sprint":
            return "live" if has_plan else "setup"
        if self.key == "data":
            return "telemetry"
        # endurance + coaching
        if has_plan:
            return "raceplan" if self.has_tab("raceplan") else self.default_tab
        if has_profiles:
            return "build" if self.has_tab("build") else self.default_tab
        return self.default_tab


# ── Registry ────────────────────────────────────────────────────────

SPRINT = ModeDescriptor(
    key="sprint",
    display_name="Sprint",
    # Ruthless default: one widget per driver decision.
    # - strategy_status: position + lap + fuel state at a glance
    # - pit_countdown: only visible in last 5 laps of stint
    # - delta_bar + sector_delta: where am I gaining/losing NOW
    # - fuel_strategy: detailed fuel if more than a glance is needed
    # - radar: traffic awareness
    # - race_reminder: surface-policy-gated carryover + low-frequency coaching;
    #   suppressed under critical alerts so it never competes with pit-now
    # Everything else is opt-in from the catalog (standings, flags, gap_timing, etc.)
    overlay_profile=frozenset({
        "strategy_status", "pit_countdown",
        "delta_bar", "sector_delta",
        "fuel_strategy",
        "radar",
        "race_reminder",
    }),
    default_tab="setup",
    available_tabs=(
        TabDef("setup", "SETUP"),
        TabDef("live", "LIVE"),
    ),
    auto_record_practice=False,
    alert_policy="critical_only",
    sync_tags=("race", "sprint"),
)

ENDURANCE = ModeDescriptor(
    key="endurance",
    display_name="Endurance",
    # Sprint + push_manage (the only extra mid-race decision in endurance)
    # + race_reminder so cross-mode coaching carryover stays visible
    # when the surface policy allows.
    overlay_profile=frozenset({
        "strategy_status", "pit_countdown",
        "delta_bar", "sector_delta",
        "fuel_strategy",
        "radar",
        "push_manage",
        "race_reminder",
    }),
    default_tab="practice",
    available_tabs=(
        TabDef("practice", "PRACTICE"),
        TabDef("build", "BUILD"),
        TabDef("raceplan", "RACE PLAN"),
    ),
    auto_record_practice=True,
    alert_policy="all",
    sync_tags=("race", "endurance", "stint"),
)

COACHING = ModeDescriptor(
    key="coaching",
    display_name="Coaching",
    # Pure self-improvement: no race chrome (no radar, no standings, no strategy)
    overlay_profile=frozenset({
        "delta_bar", "sector_delta",
        "coaching", "inputs_grip",
    }),
    default_tab="consistency",
    available_tabs=(
        TabDef("consistency", "CONSISTENCY"),
        TabDef("pace", "PACE"),
        TabDef("readiness", "READINESS"),
    ),
    auto_record_practice=True,
    alert_policy="none",
    sync_tags=("practice", "coaching"),
)

DATA = ModeDescriptor(
    key="data",
    display_name="Data",
    # Data mode is for post-session analysis; overlays are secondary.
    overlay_profile=frozenset({
        "delta_bar", "inputs_grip",
    }),
    default_tab="telemetry",
    available_tabs=(
        TabDef("telemetry", "TELEMETRY"),
        TabDef("export", "EXPORT"),
    ),
    auto_record_practice=False,
    alert_policy="none",
    sync_tags=("raw", "export"),
)

MODE_REGISTRY: dict[str, ModeDescriptor] = {
    "sprint": SPRINT,
    "endurance": ENDURANCE,
    "coaching": COACHING,
    "data": DATA,
}


def get_mode(key: str) -> ModeDescriptor:
    """Look up a mode by key, defaulting to sprint if unknown."""
    return MODE_REGISTRY.get(key, SPRINT)
