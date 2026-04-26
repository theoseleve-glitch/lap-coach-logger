"""T190: First-launch wizard renders welcome, sim detection,
and a pairing-QR prompt.

The onboarding wizard already had Welcome (step 0) and
Simulator selection (step 1). T190 adds a pairing-QR step at
position 2 — replacing the previous "You're all set" affirmation
which was UX fluff. The pairing step is now the wizard's
last screen: the user gets the QR code (or a placeholder
until the pairing-token endpoint is live in T191+) and
dismisses the wizard.

QML rendering tests are too heavy (need full Qt context); the
codebase convention since T156-T172 is *file-content pinning
via regex* on the .qml source. If the QML loader can't parse
this file, ``test_qml_bootstrap`` already catches that — these
pins guarantee the *required user-facing text and structure*
is present.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Onboarding"
    / "OnboardingFlow.qml"
)


@pytest.fixture(scope="module")
def qml_text() -> str:
    return _QML_PATH.read_text(encoding="utf-8")


# -- welcome step still present ---------------------------------------


def test_welcome_step_renders(qml_text: str) -> None:
    """Step 0 must still show the welcome message — pairing
    step replaces step 2, not step 0."""
    assert "Welcome to Lap Coach" in qml_text, (
        "Step 0 must keep the 'Welcome to Lap Coach' headline"
    )


# -- sim-detection step still present ---------------------------------


def test_sim_selection_step_renders(qml_text: str) -> None:
    """Step 1 must still ask the user which sims they drive,
    listing the four supported sims."""
    assert "Which sims do you drive?" in qml_text
    for sim in ("iRacing", "ACC", "Assetto Corsa", "Le Mans Ultimate"):
        assert sim in qml_text, (
            f"sim-detection step must list {sim!r}"
        )


# -- pairing QR step (new in T190) ------------------------------------


def test_pairing_step_has_heading(qml_text: str) -> None:
    """The pairing step must have a 'Pair' headline so the
    user understands what's being asked of them. Tolerant: any
    text containing 'Pair' inside the wizard's column."""
    assert re.search(
        r'text\s*:\s*"[^"]*Pair[^"]*"',
        qml_text,
    ), (
        "pairing step must have a Text element whose `text:` "
        "literal contains 'Pair' (e.g. 'Pair your phone')"
    )


def test_pairing_step_has_qr_placeholder(qml_text: str) -> None:
    """A QR placeholder element must be present at a stable
    id so T191's real-QR work can swap it in. The convention
    in this codebase for testing visual placeholders is a
    well-known ``id: pairingQr`` (or ``pairingQR``) element."""
    assert re.search(
        r'\bid\s*:\s*pairingQ[rR]\b',
        qml_text,
    ), (
        "pairing step must have an element with `id: pairingQr` "
        "(or `pairingQR`) so future tasks can swap in a real QR "
        "encoder without re-finding the element"
    )


def test_pairing_step_explains_action(qml_text: str) -> None:
    """The QR alone is meaningless without an explanation —
    a Text near it must tell the user to scan with their phone."""
    # Tolerant: 'Scan' anywhere in a Text literal proves the
    # call-to-action prompt is present.
    assert re.search(
        r'text\s*:\s*"[^"]*[Ss]can[^"]*"',
        qml_text,
    ), (
        "pairing step must have a Text element instructing the "
        "user to scan (e.g. 'Scan this code with your phone')"
    )


def test_pairing_step_appears_at_currentstep_two(
    qml_text: str,
) -> None:
    """Pairing must be the last step (currentStep === 2) so
    it's where the user lands when finishing sim selection."""
    # Locate the pairing step's Column block — find the line
    # containing the 'Pair' headline, then walk backward for
    # the nearest `visible: root.currentStep === N` line.
    lines = qml_text.splitlines()
    pair_line_idx = None
    for i, line in enumerate(lines):
        if "Pair" in line and re.search(r'text\s*:\s*"[^"]*Pair', line):
            pair_line_idx = i
            break
    assert pair_line_idx is not None, (
        "couldn't locate the 'Pair' headline line in the QML"
    )
    # Walk backward looking for the visible-currentStep line.
    visible_step = None
    for i in range(pair_line_idx, -1, -1):
        match = re.search(
            r'visible\s*:\s*root\.currentStep\s*===\s*(\d+)',
            lines[i],
        )
        if match:
            visible_step = int(match.group(1))
            break
    assert visible_step == 2, (
        f"pairing step must be at currentStep === 2 (last "
        f"step in a 3-step flow); found at currentStep === "
        f"{visible_step}"
    )


def test_pairing_step_dismisses_wizard(qml_text: str) -> None:
    """The pairing step must have a button that dismisses the
    wizard — otherwise the user is trapped on the QR screen.
    This is the existing 'Get Started'/'Done'/onboardingVM.finish()
    behaviour that previously lived on the 'You're all set'
    step."""
    # Tolerant: must reference dismissed=true OR finish().
    has_dismiss = (
        "root.dismissed = true" in qml_text
        or "onboardingVM.finish" in qml_text
    )
    assert has_dismiss, (
        "wizard must have a dismiss action — either "
        "`root.dismissed = true` or `onboardingVM.finish()` "
        "must appear so the user can exit the wizard"
    )
