"""T053: Multi-account scaffold — ``AccountRegistry`` tracks known accounts.

ADR-011 (Q63) says "1 user = 1 DriverProfile" for v1, but the
overall design supports multiple accounts later. The keychain
itself can hold multiple account entries (it's account-keyed) but
provides no enumeration. ``AccountRegistry`` plugs that gap: it
records which accounts exist and which one is currently active,
persisted in a JSON file under ``config_dir()`` so the wiring can
re-instantiate ``PairingViewModel(known_account=...)`` on next
launch with the right account.

In M1 only one account is ever added — the surface is multi-aware
so a future picker UI can land without changing call sites.

Tests use a per-test ``tmp_path`` so the registry's JSON file is
hermetic and doesn't touch the user's real config dir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Empty / cold-start state
# ---------------------------------------------------------------------------


def test_fresh_registry_has_no_accounts(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")

    assert reg.active_account is None
    assert reg.accounts == ()


def test_missing_state_file_is_treated_as_empty(tmp_path: Path) -> None:
    """Cold-start with no persisted state must not raise."""
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "does-not-exist.json")
    assert reg.active_account is None
    assert reg.accounts == ()


# ---------------------------------------------------------------------------
# add_account
# ---------------------------------------------------------------------------


def test_first_added_account_becomes_active_automatically(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")

    assert reg.active_account == "alice@example.com"
    assert reg.accounts == ("alice@example.com",)


def test_second_added_account_does_not_change_active(tmp_path: Path) -> None:
    """Future multi-account UX: explicit switching, not implicit."""
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")
    reg.add_account("bob@example.com")

    assert reg.active_account == "alice@example.com"
    assert reg.accounts == ("alice@example.com", "bob@example.com")


def test_adding_existing_account_is_idempotent(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")
    reg.add_account("alice@example.com")

    assert reg.accounts == ("alice@example.com",)


def test_add_account_rejects_empty_name(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    with pytest.raises(ValueError):
        reg.add_account("")
    with pytest.raises(ValueError):
        reg.add_account("   ")


# ---------------------------------------------------------------------------
# set_active
# ---------------------------------------------------------------------------


def test_set_active_switches_to_a_known_account(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")
    reg.add_account("bob@example.com")

    reg.set_active("bob@example.com")

    assert reg.active_account == "bob@example.com"


def test_set_active_unknown_account_raises(tmp_path: Path) -> None:
    """Don't silently accept a typo — surface it loudly."""
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")

    with pytest.raises(ValueError):
        reg.set_active("nobody@example.com")
    assert reg.active_account == "alice@example.com"


# ---------------------------------------------------------------------------
# remove_account
# ---------------------------------------------------------------------------


def test_remove_account_drops_from_list(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")
    reg.add_account("bob@example.com")

    reg.remove_account("bob@example.com")

    assert reg.accounts == ("alice@example.com",)
    assert reg.active_account == "alice@example.com"


def test_removing_active_account_falls_back_to_remaining(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")
    reg.add_account("bob@example.com")
    reg.set_active("alice@example.com")

    reg.remove_account("alice@example.com")

    assert reg.accounts == ("bob@example.com",)
    assert reg.active_account == "bob@example.com"


def test_removing_last_account_clears_active(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("solo@example.com")

    reg.remove_account("solo@example.com")

    assert reg.accounts == ()
    assert reg.active_account is None


def test_removing_unknown_account_is_idempotent(tmp_path: Path) -> None:
    """Sign-out flows should be safe to call without checking existence."""
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")

    # Must not raise.
    reg.remove_account("never-added@example.com")


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


def test_clear_empties_the_registry(tmp_path: Path) -> None:
    from lap_coach_logger.account_registry import AccountRegistry

    reg = AccountRegistry(state_path=tmp_path / "accounts.json")
    reg.add_account("alice@example.com")
    reg.add_account("bob@example.com")

    reg.clear()

    assert reg.accounts == ()
    assert reg.active_account is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_state_persists_across_instances(tmp_path: Path) -> None:
    """Restart simulation: a fresh AccountRegistry on the same path
    must observe what the previous instance recorded."""
    from lap_coach_logger.account_registry import AccountRegistry

    state_path = tmp_path / "accounts.json"
    reg1 = AccountRegistry(state_path=state_path)
    reg1.add_account("alice@example.com")
    reg1.add_account("bob@example.com")
    reg1.set_active("bob@example.com")

    reg2 = AccountRegistry(state_path=state_path)

    assert reg2.accounts == ("alice@example.com", "bob@example.com")
    assert reg2.active_account == "bob@example.com"


def test_persisted_file_is_human_readable_json(tmp_path: Path) -> None:
    """Important for support / debugging — a user should be able to
    open the file and see what's there."""
    from lap_coach_logger.account_registry import AccountRegistry

    state_path = tmp_path / "accounts.json"
    reg = AccountRegistry(state_path=state_path)
    reg.add_account("alice@example.com")

    parsed = json.loads(state_path.read_text(encoding="utf-8"))
    assert parsed.get("active") == "alice@example.com"
    assert parsed.get("accounts") == ["alice@example.com"]


def test_corrupt_state_file_falls_back_to_empty(tmp_path: Path) -> None:
    """A garbled JSON file (e.g. crashed write) must not crash the app."""
    from lap_coach_logger.account_registry import AccountRegistry

    state_path = tmp_path / "accounts.json"
    state_path.write_text("{not valid json", encoding="utf-8")

    reg = AccountRegistry(state_path=state_path)

    assert reg.accounts == ()
    assert reg.active_account is None


# ---------------------------------------------------------------------------
# Single-account M1 flow (acceptance: "single-account works")
# ---------------------------------------------------------------------------


def test_single_account_m1_flow_end_to_end(tmp_path: Path) -> None:
    """Pair once → registry has exactly one account, that account is
    active, and the state survives a restart so the VM can rehydrate
    on next launch with the correct ``known_account``."""
    from lap_coach_logger.account_registry import AccountRegistry

    state_path = tmp_path / "accounts.json"
    reg = AccountRegistry(state_path=state_path)

    # Imagine PairingClient returns this account name on a 200.
    reg.add_account("theos.eleve@gmail.com")

    assert reg.active_account == "theos.eleve@gmail.com"
    assert reg.accounts == ("theos.eleve@gmail.com",)

    # Restart.
    reg2 = AccountRegistry(state_path=state_path)
    assert reg2.active_account == "theos.eleve@gmail.com"
