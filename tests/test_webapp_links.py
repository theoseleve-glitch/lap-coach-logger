"""T070: ``utils.webapp_links`` builds the URLs the desktop opens
when the user picks "View in webapp".

Per Q95, the desktop pushes export/analysis flows to the webapp;
the desktop side just needs a URL builder + an opener seam.

Helpers covered:

* ``webapp_base_url()``           — env-overridable base
* ``view_sessions_url()``         — list view (default landing)
* ``view_session_url(session_id)`` — per-session deep link
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# webapp_base_url
# ---------------------------------------------------------------------------


def test_default_base_url_is_production_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.webapp_links import webapp_base_url

    monkeypatch.delenv("LAP_COACH_WEBAPP_URL", raising=False)

    assert webapp_base_url() == "https://app.lap-coach.racing"


def test_env_var_overrides_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Staging/dev builds point at a non-prod webapp via env var."""
    from lap_coach_logger.utils.webapp_links import webapp_base_url

    monkeypatch.setenv("LAP_COACH_WEBAPP_URL", "https://staging.lap-coach.racing")

    assert webapp_base_url() == "https://staging.lap-coach.racing"


def test_env_var_override_strips_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trailing slash on the override would double-slash the path
    in subsequent f-strings — normalise once at the source."""
    from lap_coach_logger.utils.webapp_links import webapp_base_url

    monkeypatch.setenv("LAP_COACH_WEBAPP_URL", "https://staging.lap-coach.racing/")

    assert webapp_base_url() == "https://staging.lap-coach.racing"


# ---------------------------------------------------------------------------
# view_sessions_url
# ---------------------------------------------------------------------------


def test_view_sessions_url_appends_sessions_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lap_coach_logger.utils.webapp_links import view_sessions_url

    monkeypatch.delenv("LAP_COACH_WEBAPP_URL", raising=False)

    assert view_sessions_url() == "https://app.lap-coach.racing/sessions"


# ---------------------------------------------------------------------------
# view_session_url
# ---------------------------------------------------------------------------


def test_view_session_url_includes_session_id() -> None:
    from lap_coach_logger.utils.webapp_links import view_session_url

    url = view_session_url("01900000-0000-7000-8000-00000000a070")

    assert url.endswith("/sessions/01900000-0000-7000-8000-00000000a070")


def test_view_session_url_falls_back_to_list_when_id_blank() -> None:
    """A missing session_id from QML must NOT produce a /sessions/
    URL with an empty trailing segment (which would 404 on the
    webapp). Fall back to the list view."""
    from lap_coach_logger.utils.webapp_links import view_session_url

    assert view_session_url("") == "https://app.lap-coach.racing/sessions"
    assert view_session_url("   ") == "https://app.lap-coach.racing/sessions"


def test_view_session_url_strips_whitespace() -> None:
    """Some review data dicts arrive with stringified UUIDs that
    carry trailing whitespace — defensive normalize."""
    from lap_coach_logger.utils.webapp_links import view_session_url

    url = view_session_url("  abc-123\n")

    assert url.endswith("/sessions/abc-123")
