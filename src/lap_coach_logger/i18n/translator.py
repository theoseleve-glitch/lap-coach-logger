"""Translator with locale fallback chain.

  - English ("en") is the source-of-truth catalog.
  - Other locales (FR for now) fall back to English on missing
    keys, so partial translations work fine.
  - Unknown keys return the key itself (logged once) — visible
    in the UI as ``foo.bar.baz`` rather than crashing.
"""
from __future__ import annotations

import logging

from lap_coach_logger.i18n.strings import en, fr

_log = logging.getLogger(__name__)

# Fallback chain: each locale → list of catalogs to consult in
# order. English is always the final fallback so seed coverage in
# en.STRINGS == full UI coverage.
_CATALOGS: dict[str, tuple[dict[str, str], ...]] = {
    "en": (en.STRINGS,),
    "fr": (fr.STRINGS, en.STRINGS),
}


def available_locales() -> tuple[str, ...]:
    """Locales the translator knows about. Adding a new locale =
    add a ``strings/<code>.py`` module and an entry to
    ``_CATALOGS``."""
    return tuple(_CATALOGS.keys())


class Translator:
    """Locale-aware string lookup."""

    def __init__(self, locale: str = "en") -> None:
        if locale not in _CATALOGS:
            raise ValueError(
                f"unknown locale {locale!r}; "
                f"available: {sorted(_CATALOGS.keys())}"
            )
        self._locale = locale

    @property
    def locale(self) -> str:
        return self._locale

    def set_locale(self, locale: str) -> None:
        """Switch active locale. Raises on unknown codes — silent
        ignore would leave the UI in an unexpected language."""
        if locale not in _CATALOGS:
            raise ValueError(
                f"unknown locale {locale!r}; "
                f"available: {sorted(_CATALOGS.keys())}"
            )
        self._locale = locale

    def t(self, key: str) -> str:
        """Look up ``key`` in the active locale, falling back
        through the chain to English. If nothing matches, return
        the key itself (so missing strings are visible in the UI
        rather than crashing)."""
        for catalog in _CATALOGS[self._locale]:
            if key in catalog:
                return catalog[key]
        _log.debug("i18n: missing key %r in locale %r", key, self._locale)
        return key


# Module-level default Translator. Most call sites use the
# convenience ``t(key)`` rather than constructing their own.
_default = Translator()


def t(key: str) -> str:
    """Look up ``key`` in the default Translator's active locale."""
    return _default.t(key)


def set_default_locale(locale: str) -> None:
    """Switch the default Translator's locale (e.g. on startup
    after reading user preference)."""
    _default.set_locale(locale)
