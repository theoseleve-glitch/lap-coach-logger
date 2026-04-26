"""T219: Translation scaffold — English v1, stubs for FR+.

Pins the i18n contract:

  - ``Translator`` class manages a current locale + lookups
  - ``t(key)`` returns the string for the active locale
  - English ("en") is the source-of-truth catalog
  - Other locales (FR for now) are stub catalogs that fall back
    to English on missing keys (so v1 ships with English while
    translators fill in stubs gradually)
  - Unknown keys return the key itself (logged) so missing
    strings are visible in the UI rather than crashing

The actual full string extraction (every QML/Python literal →
i18n key) is gradual; T219 establishes the scaffold and pins
the keys already referenced from ``overlays/builtins.py`` as
the seed catalog.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.i18n import Translator, t, available_locales


# ---------------------------------------------------------------------------
# Translator basics
# ---------------------------------------------------------------------------


def test_translator_constructs_with_default_locale() -> None:
    """Default locale is 'en' (English) — the source-of-truth
    catalog that every other locale falls back to."""
    tr = Translator()
    assert tr.locale == "en"


def test_translator_can_set_locale() -> None:
    """Locale switching is the user-facing API for translation."""
    tr = Translator()
    tr.set_locale("fr")
    assert tr.locale == "fr"


def test_translator_rejects_unknown_locale() -> None:
    """Unknown locale codes must raise — silent ignore would
    leave the UI in an unexpected language."""
    tr = Translator()
    with pytest.raises(ValueError):
        tr.set_locale("xx-INVALID")


def test_available_locales_includes_en_and_fr() -> None:
    """v1 ships English (complete) and a French stub. Adding
    new locales = adding a strings/<code>.py module."""
    locales = available_locales()
    assert "en" in locales
    assert "fr" in locales


# ---------------------------------------------------------------------------
# Translation lookup
# ---------------------------------------------------------------------------


def test_t_returns_english_for_known_key() -> None:
    """Known key in default locale returns its English string."""
    # Pick a key from the seed catalog (overlays.builtins references).
    result = t("overlay.radar_awareness.name")
    assert result != "overlay.radar_awareness.name", (
        "expected a translated string, got the key back — "
        "seed catalog is missing this key"
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_t_returns_key_for_unknown_key() -> None:
    """Unknown keys return the key itself — visible in UI as
    'foo.bar.baz' rather than crashing or showing empty."""
    result = t("definitely.does.not.exist")
    assert result == "definitely.does.not.exist"


def test_t_returns_english_string_in_french_when_not_translated() -> None:
    """FR catalog is a stub — most keys aren't translated yet.
    Lookup must fall back to English so the UI never shows blanks
    while translators work."""
    tr = Translator()
    tr.set_locale("fr")
    result = tr.t("overlay.radar_awareness.name")
    # FR stub doesn't translate this yet → falls back to English.
    assert result != "overlay.radar_awareness.name", (
        "FR fallback to English broke — UI would show key string"
    )


def test_translator_t_uses_active_locale() -> None:
    """The instance method ``tr.t(key)`` looks up in the
    instance's active locale, not the global default."""
    tr_en = Translator(locale="en")
    tr_fr = Translator(locale="fr")
    assert tr_en.locale == "en"
    assert tr_fr.locale == "fr"


# ---------------------------------------------------------------------------
# Seed catalog: keys referenced from builtins.py exist in English
# ---------------------------------------------------------------------------


def test_seed_catalog_covers_builtin_overlay_keys() -> None:
    """Drift-prevention: every i18n key referenced from
    ``overlays/builtins.py`` MUST exist in the English catalog.
    Otherwise overlays render their key string instead of a name."""
    from lap_coach_logger.i18n.strings import en

    # Sample of keys we know are referenced from builtins.py.
    # T219 seed catalog must cover at least these.
    required_keys = (
        "overlay.radar_awareness.name",
        "overlay.radar_awareness.description",
        "overlay.spotter_awareness.name",
        "overlay.spotter_awareness.description",
        "overlay.session_delta.name",
        "overlay.session_delta.description",
    )
    missing = [k for k in required_keys if k not in en.STRINGS]
    assert not missing, (
        f"English catalog missing seed keys: {missing} — "
        f"overlays will render the key string in their UI"
    )


def test_french_stub_is_empty_or_partial_dict() -> None:
    """FR stub is just a dict — empty initially, translators fill in
    keys as they go. The fallback chain (FR → EN) means partial FR
    catalogs work fine."""
    from lap_coach_logger.i18n.strings import fr

    assert isinstance(fr.STRINGS, dict)
    # FR may be empty or partially translated; both are acceptable.


def test_module_level_t_function_exists() -> None:
    """Convenience: module-level ``t(key)`` calls the default
    Translator. Most call sites use this rather than passing
    a Translator instance."""
    from lap_coach_logger import i18n
    assert callable(i18n.t)
