"""i18n scaffold (T219).

  - ``Translator`` manages a current locale and string lookup.
  - ``t(key)`` is the convenience module-level function backed by
    a default Translator.
  - English is the source-of-truth catalog; other locales fall
    back to it for any key they don't translate yet.
"""
from __future__ import annotations

from lap_coach_logger.i18n.translator import (
    Translator,
    available_locales,
    set_default_locale,
    t,
)

__all__ = ["Translator", "t", "available_locales", "set_default_locale"]
