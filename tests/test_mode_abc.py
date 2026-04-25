"""T106: ``Mode`` ABC in ``core/modes/base.py``.

Defines the contract every mode subclass (T107 PracticeMode,
T108 SprintMode, T109 EnduranceMode, T110 ReviewMode) must
satisfy. The ABC has four abstract members because modes
bind four orthogonal dimensions per Q96:

- ``id``: stable string for serialization (settings persistence)
- ``name``: display string for the toolbar dropdown (T116)
- ``coaching_verbosity``: "off" / "minimal" / "verbose"
  drives T113's coaching cadence
- ``overlay_preset_id``: which preset (T121-T125) the mode
  binds — drives T112's switch behaviour
- ``environment_tag``: per-mode tag stamped on finalize
  bundles (T115) — server uses for cross-session aggregation
- ``strategy_safety_margin``: scalar for T114's strategy
  assumptions — % overhead on fuel / time predictions

Why concrete properties (not raw abstract methods): subclasses
just declare class-level constants, no work. Mode instances
are stateless and shareable. T111's ModeEngine instantiates
each subclass once and dispatches on ``id``.
"""
from __future__ import annotations

import inspect

import pytest

from lap_coach_logger.core.modes.base import Mode


# ---------------------------------------------------------------------------
# Mode is an ABC — can't instantiate directly
# ---------------------------------------------------------------------------


def test_mode_is_abstract_and_cannot_be_instantiated() -> None:
    """The ABC's role is to enforce the contract on subclasses;
    instantiating the bare ABC is a programmer error worth
    surfacing immediately."""
    assert inspect.isabstract(Mode)
    with pytest.raises(TypeError):
        Mode()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Required abstract members
# ---------------------------------------------------------------------------


def test_mode_declares_id_property() -> None:
    """``id`` is the serialization key (settings persistence,
    T117). Subclasses MUST override; the ABC stays abstract on
    this property."""
    assert "id" in Mode.__abstractmethods__


def test_mode_declares_name_property() -> None:
    """``name`` is the user-facing label (T116 toolbar)."""
    assert "name" in Mode.__abstractmethods__


def test_mode_declares_coaching_verbosity_property() -> None:
    """``coaching_verbosity`` drives T113. Three values:
    ``"off"`` / ``"minimal"`` / ``"verbose"``."""
    assert "coaching_verbosity" in Mode.__abstractmethods__


def test_mode_declares_overlay_preset_id_property() -> None:
    """``overlay_preset_id`` binds the mode to a preset (T112,
    T121-T125)."""
    assert "overlay_preset_id" in Mode.__abstractmethods__


def test_mode_declares_environment_tag_property() -> None:
    """``environment_tag`` stamps the finalize bundle (T115) so
    the server can aggregate sessions by mode."""
    assert "environment_tag" in Mode.__abstractmethods__


def test_mode_declares_strategy_safety_margin_property() -> None:
    """``strategy_safety_margin`` (T114) — scalar applied to
    fuel / time predictions for the mode's risk profile."""
    assert "strategy_safety_margin" in Mode.__abstractmethods__


# ---------------------------------------------------------------------------
# Concrete subclasses pass the contract
# ---------------------------------------------------------------------------


def test_concrete_subclass_implementing_all_abstract_members_can_instantiate() -> None:
    """Pin that the abstract surface is reachable by a vanilla
    subclass — class-level constants suffice, no funky metaclass
    rules. T107-T110 will follow this exact pattern."""

    class _ConcreteTestMode(Mode):
        id = "test"
        name = "Test"
        coaching_verbosity = "minimal"
        overlay_preset_id = "race-minimal"
        environment_tag = "sim_test"
        strategy_safety_margin = 0.10

    instance = _ConcreteTestMode()  # type: ignore[abstract]
    assert instance.id == "test"
    assert instance.name == "Test"
    assert instance.coaching_verbosity == "minimal"
    assert instance.overlay_preset_id == "race-minimal"
    assert instance.environment_tag == "sim_test"
    assert instance.strategy_safety_margin == pytest.approx(0.10)


def test_subclass_missing_a_required_member_cannot_instantiate() -> None:
    """Defensive — a subclass that forgets one of the abstract
    members must fail at instantiation time (Python's ABC
    machinery), not silently inherit ``None``."""

    class _IncompleteMode(Mode):
        id = "incomplete"
        name = "Incomplete"
        # Missing: coaching_verbosity, overlay_preset_id,
        # environment_tag, strategy_safety_margin

    with pytest.raises(TypeError):
        _IncompleteMode()  # type: ignore[abstract]
