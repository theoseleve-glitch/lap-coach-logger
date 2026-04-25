"""T181: Inno Setup uninstaller cleans all files + registry entries.

The app writes a Windows autostart registry value at runtime
(``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``,
value name ``LapCoach.Logger``) when the user opts into
"start with Windows". If the user later uninstalls the app
without first turning off autostart, Windows will keep trying
to launch a missing executable at every login.

Inno's installer cleans its own per-AppId metadata + the
``{app}`` install dir automatically. Cleanup of *runtime-written*
registry values has to be declared explicitly via a ``[Registry]``
entry with ``Flags: uninsdeletevalue``.

T181 pins three uninstaller cleanup properties of the .iss:

1. The .iss does not opt out of producing an uninstaller
   (``Uninstallable=no`` would suppress it entirely).
2. The ``[UninstallDelete]`` section removes the ``{app}``
   tree (any leftover user-modified files).
3. A ``[Registry]`` entry tracks the autostart value for
   uninstall-time deletion — matched by:
   - ``Root: HKCU``,
   - ``Subkey: ...\\Run``,
   - ``ValueName: LapCoach.Logger``,
   - ``Flags: ...uninsdeletevalue...``.

Source-content pin (consistent with T175-T180).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ISS_PATH = (
    Path(__file__).resolve().parents[1]
    / "installer" / "LapCoachLogger.iss"
)


@pytest.fixture(scope="module")
def iss_text() -> str:
    return _ISS_PATH.read_text(encoding="utf-8")


def _setup_section(iss_text: str) -> str:
    match = re.search(
        r'\[Setup\]([\s\S]*?)(?=\n\[\w+\]|\Z)',
        iss_text,
    )
    assert match is not None, ".iss must have a [Setup] section"
    return match.group(1)


def _section_body(iss_text: str, section: str) -> str:
    match = re.search(
        rf'\[{re.escape(section)}\]([\s\S]*?)(?=\n\[\w+\]|\Z)',
        iss_text,
    )
    assert match is not None, f".iss must have [{section}] section"
    return match.group(1)


# -- Uninstaller is produced ------------------------------------------


def test_iss_does_not_opt_out_of_uninstaller(iss_text: str) -> None:
    """``Uninstallable=no`` would suppress the uninstaller
    entirely. T181 explicitly requires uninstall to work."""
    setup = _setup_section(iss_text)
    match = re.search(
        r'^\s*Uninstallable\s*=\s*(\w+)',
        setup,
        re.MULTILINE,
    )
    if match is not None:
        value = match.group(1).lower()
        assert value != "no", (
            "Uninstallable=no would suppress uninstaller "
            "generation — T181 requires either omitting the "
            "directive (defaults to yes) or setting it to `yes`"
        )


# -- Files cleaned up --------------------------------------------------


def test_iss_uninstall_delete_removes_app_dir(iss_text: str) -> None:
    """``[UninstallDelete]`` must include a ``filesandordirs``
    entry for ``{app}`` so user-modified files left in the
    install dir don't orphan after uninstall."""
    body = _section_body(iss_text, "UninstallDelete")
    found = False
    for line in body.splitlines():
        # Tolerant: line must mention `filesandordirs` and `{app}`
        if "filesandordirs" in line and "{app}" in line:
            found = True
            break
    assert found, (
        "[UninstallDelete] must have a "
        "`Type: filesandordirs; Name: \"{app}\"` entry to clean "
        "the install dir on uninstall"
    )


# -- Autostart registry value cleaned up -------------------------------


def test_iss_uninstall_cleans_autostart_registry_value(
    iss_text: str,
) -> None:
    """The .iss must declare a ``[Registry]`` entry tracking
    the runtime-written autostart value
    (``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``,
    name = ``LapCoach.Logger``) for uninstall-time deletion via
    the ``uninsdeletevalue`` flag.

    Without this, uninstalling the app leaves Windows trying to
    launch a missing exe at every login — orphan-state bug.
    """
    body = _section_body(iss_text, "Registry")
    # Tolerant match: at least one line must reference the
    # autostart Run subkey, the LapCoach.Logger value name, and
    # the uninsdeletevalue flag. Inno Setup uses `;` as a
    # field separator inside [Registry] entries, so we match
    # the entire line (skipping only fully-commented `;` lines).
    autostart_line = None
    for line in body.splitlines():
        if line.lstrip().startswith(";"):
            continue
        if "Run" not in line:
            continue
        if "LapCoach.Logger" not in line:
            continue
        if "uninsdeletevalue" not in line:
            continue
        autostart_line = line
        break

    assert autostart_line is not None, (
        "[Registry] must include an entry referencing the "
        "Windows autostart Run subkey, the `LapCoach.Logger` "
        "value name, and `uninsdeletevalue` flag — otherwise "
        "uninstalling the app leaves an orphan autostart entry "
        "pointing at a deleted exe."
    )

    # Sanity: the entry should be HKCU (the app writes there at
    # runtime via winreg.HKEY_CURRENT_USER).
    assert "HKCU" in autostart_line, (
        f"Autostart [Registry] entry should target HKCU "
        f"(matching set_autostart's HKEY_CURRENT_USER write), "
        f"got: {autostart_line!r}"
    )


def test_iss_autostart_registry_entry_does_not_create_value(
    iss_text: str,
) -> None:
    """The autostart [Registry] entry must NOT write a value at
    install time — the app writes it at runtime when the user
    opts into autostart. Using ``ValueType: none`` makes the
    entry a tracker-only declaration.

    Tolerant: accept either ``ValueType: none`` or a
    ``dontcreatekey`` flag on the autostart line."""
    body = _section_body(iss_text, "Registry")
    autostart_line = None
    for line in body.splitlines():
        if line.lstrip().startswith(";"):
            continue
        if "Run" in line and "LapCoach.Logger" in line and "uninsdeletevalue" in line:
            autostart_line = line
            break
    assert autostart_line is not None, (
        "Precondition: autostart [Registry] line must exist "
        "(see test_iss_uninstall_cleans_autostart_registry_value)"
    )

    # Either explicit ValueType: none, or dontcreatekey flag.
    has_none = re.search(
        r'ValueType\s*:\s*none\b',
        autostart_line,
        re.IGNORECASE,
    )
    has_dontcreate = "dontcreatekey" in autostart_line.lower()
    assert has_none or has_dontcreate, (
        f"Autostart [Registry] entry must use `ValueType: none` "
        f"or `dontcreatekey` to avoid writing the autostart "
        f"value at install time (the app writes it at runtime), "
        f"got: {autostart_line!r}"
    )
