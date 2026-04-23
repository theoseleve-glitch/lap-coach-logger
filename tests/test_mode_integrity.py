"""Tests for default overlay profile integrity and cognitive-load limits.

After the ruthless cut in redesign v2, each mode has a specific,
opinionated default set. These tests lock in that shape so future
'just enable one more widget' creep is caught.
"""

from __future__ import annotations

from lap_coach_logger.core.mode_descriptor import (
    COACHING,
    DATA,
    ENDURANCE,
    SPRINT,
    MODE_REGISTRY,
)
from lap_coach_logger.viewmodels.overlay_helpers import (
    OVERLAY_TIERS,
    get_widget_tier,
)


# Widgets that are dangerous to show while driving.
# If any mode enables these by default, it's a product regression.
TEXT_HEAVY_WIDGETS = frozenset({
    "standings_table", "leaderboard", "head_to_head",
    "advanced_panel", "data_blocks",
    "chat", "chat_highlight", "chat_race_game", "chat_race_standing",
    "custom_text", "custom_url", "promo_code_alert",
})


class TestModeDefaultsAreBounded:
    """No mode should enable too many widgets by default."""

    def test_sprint_has_at_most_8_widgets(self) -> None:
        assert len(SPRINT.overlay_profile) <= 8, (
            f"Sprint default bloated: {len(SPRINT.overlay_profile)} widgets "
            f"({sorted(SPRINT.overlay_profile)})"
        )

    def test_endurance_has_at_most_10_widgets(self) -> None:
        assert len(ENDURANCE.overlay_profile) <= 10

    def test_coaching_has_at_most_6_widgets(self) -> None:
        # Coaching mode is for focus — strictly minimal.
        assert len(COACHING.overlay_profile) <= 6

    def test_data_has_at_most_4_widgets(self) -> None:
        # Data mode overlays are secondary (Data is post-session first).
        assert len(DATA.overlay_profile) <= 4


class TestNoTextHeavyWidgetsByDefault:
    """Text-heavy widgets are a distraction risk while driving."""

    def test_sprint_has_no_text_heavy_defaults(self) -> None:
        overlap = SPRINT.overlay_profile & TEXT_HEAVY_WIDGETS
        assert not overlap, f"Sprint enables text-heavy widgets by default: {overlap}"

    def test_endurance_has_no_text_heavy_defaults(self) -> None:
        overlap = ENDURANCE.overlay_profile & TEXT_HEAVY_WIDGETS
        assert not overlap, f"Endurance enables text-heavy widgets by default: {overlap}"

    def test_coaching_has_no_text_heavy_defaults(self) -> None:
        overlap = COACHING.overlay_profile & TEXT_HEAVY_WIDGETS
        assert not overlap, f"Coaching enables text-heavy widgets by default: {overlap}"

    def test_data_has_no_text_heavy_defaults(self) -> None:
        overlap = DATA.overlay_profile & TEXT_HEAVY_WIDGETS
        assert not overlap, f"Data enables text-heavy widgets by default: {overlap}"


class TestAllDefaultsAreInCoreOrCoaching:
    """Every default widget must be in the core_race or coaching tier.

    If it's optional, it should not be enabled by default — that's what
    the Optional Pack toggle is for.
    """

    def _check(self, descriptor, allowed_tiers: set[str]) -> None:
        for widget in descriptor.overlay_profile:
            tier = get_widget_tier(widget)
            assert tier in allowed_tiers, (
                f"{descriptor.key} enables {widget!r} (tier={tier}) by default, "
                f"but only {allowed_tiers} are allowed"
            )

    def test_sprint_only_uses_core_race(self) -> None:
        self._check(SPRINT, {"core_race"})

    def test_endurance_only_uses_core_race(self) -> None:
        self._check(ENDURANCE, {"core_race"})

    def test_coaching_uses_core_or_coaching(self) -> None:
        # Coaching mode can use coaching-tier widgets. Core is also fine
        # (delta_bar, sector_delta are core).
        self._check(COACHING, {"core_race", "coaching"})

    def test_data_uses_core_or_coaching(self) -> None:
        self._check(DATA, {"core_race", "coaching"})


class TestEveryModeHasEssentials:
    """Each race mode must surface its essentials."""

    def test_sprint_has_strategy_status(self) -> None:
        assert "strategy_status" in SPRINT.overlay_profile, \
            "Sprint must show the always-on strategy banner"

    def test_sprint_has_pit_countdown(self) -> None:
        assert "pit_countdown" in SPRINT.overlay_profile

    def test_sprint_has_sector_delta(self) -> None:
        assert "sector_delta" in SPRINT.overlay_profile

    def test_sprint_has_fuel_widget(self) -> None:
        assert "fuel_strategy" in SPRINT.overlay_profile

    def test_endurance_has_push_manage(self) -> None:
        assert "push_manage" in ENDURANCE.overlay_profile, \
            "Endurance must show push/manage decision"

    def test_coaching_has_coaching_card(self) -> None:
        assert "coaching" in COACHING.overlay_profile

    def test_coaching_has_no_radar(self) -> None:
        assert "radar" not in COACHING.overlay_profile, \
            "Coaching mode strips race awareness for focus"

    def test_coaching_has_no_standings(self) -> None:
        assert "standings" not in COACHING.overlay_profile

    def test_coaching_has_no_strategy_status(self) -> None:
        assert "strategy_status" not in COACHING.overlay_profile


class TestRegistryConsistency:
    def test_all_registry_modes_declared(self) -> None:
        assert set(MODE_REGISTRY.keys()) == {"sprint", "endurance", "coaching", "data"}

    def test_every_default_widget_has_a_tier(self) -> None:
        """No orphan widgets — every default widget must be categorized."""
        all_defaults: set[str] = set()
        for desc in MODE_REGISTRY.values():
            all_defaults.update(desc.overlay_profile)
        for widget in all_defaults:
            tier = get_widget_tier(widget)
            assert tier != "optional", (
                f"{widget!r} is enabled by default in some mode but "
                f"tiered as 'optional' — update OVERLAY_TIERS"
            )
