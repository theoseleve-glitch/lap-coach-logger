# RC1 Release — Lap Coach Logger

> **Status:** Release Candidate 1. Unsigned. Windows x64 only.
> **Maintainer:** release engineer on duty.
> **Single source of truth:** `src/lap_coach_logger/app_identity.py` → `VERSION = "2.0.0"`.

## 1. Prerequisites

Install once per build machine:

| Requirement | Exact version | How to verify |
|---|---|---|
| Windows 10/11 x64 | — | `winver` |
| Python | **3.12.x** (no other minor) | `python --version` → `Python 3.12.*` |
| Inno Setup 6 | 6.x | `ISCC.exe /?` resolves |
| git | any recent | `git --version` |

The build script refuses any Python != 3.12 — this is intentional. 3.14 has traceback/signal quirks that break log dedup, 3.11 predates runtime primitives the code relies on.

## 2. Pre-flight checks

1. Working tree is clean: `git status` shows nothing.
2. Tests pass on the current branch: `python -m pytest tests/ -q` → all green.
3. `VERSION` in `src/lap_coach_logger/app_identity.py` matches the target release (e.g. `2.0.0` for RC1).
4. `assets/icon.ico` exists.
5. Inno Setup is installed (checked by `build_installer.bat`).

## 3. Build

One command from repo root:

```bat
scripts\build_rc1.bat
```

What it does (9 steps, fails fast on any):

1. Enforces CPython 3.12.x on x64. PyPy / free-threaded / ARM64 all fail.
2. Enforces clean git tree. Override with `scripts\build_rc1.bat --allow-dirty` for emergency patches — the resulting `build_info.json` will have `git_dirty=true`.
3. Wipes `dist\`, `build\LapCoachLogger\`, `__pycache__`, prior installers.
4. Installs build deps (`pip install -e ".[build,dev]"`) with `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, `PIP_CONFIG_FILE=NUL`, and `SOURCE_DATE_EPOCH` pinned to the HEAD commit time — for reproducibility.
5. Runs the full test suite (same exclusions as CI).
6. Regenerates `build\windows\version_info.txt` from `app_identity.VERSION`.
7. Runs PyInstaller (`--noconfirm --clean`) → `dist\LapCoachLogger\`.
8. Writes `dist\LapCoachLogger\build_info.json` with version, git SHA, `git_dirty`, Python version + implementation, `pip_freeze_sha256_16`, UTC timestamp, platform.
9. Builds the Inno Setup installer → `LapCoachLogger-Setup-2.0.0.exe` at repo root.

Expected output on success:

```
=== RC1 BUILD SUCCESSFUL ===
  Frozen folder:  dist\LapCoachLogger\
  Build info:     dist\LapCoachLogger\build_info.json
  Installer:      LapCoachLogger-Setup-*.exe
```

## 4. Smoke tests

Run immediately after the build:

```bat
scripts\run_smoke_tests.bat
```

Validates:

- `dist\LapCoachLogger\LapCoachLogger.exe` exists and is > 1 MB.
- `dist\LapCoachLogger\build_info.json` exists.
- Launching the exe reaches `All backend services running – launching QML shell` in the runtime log within 25 s.
- No `CRITICAL` log lines in the startup window.
- The process terminates cleanly on SIGTERM.

Exit code 0 = pass. Any failure prints the last 20 captured log lines.

## 5. Artifact locations

| Artifact | Path | Purpose |
|---|---|---|
| Frozen app folder | `dist\LapCoachLogger\` | Raw PyInstaller output, ~150 MB |
| Main exe | `dist\LapCoachLogger\LapCoachLogger.exe` | Entry point |
| Build metadata | `dist\LapCoachLogger\build_info.json` | Version + SHA + timestamp trail |
| Windows installer | `LapCoachLogger-Setup-2.0.0.exe` (repo root) | What ships to testers |
| Runtime log (after launch) | `%LOCALAPPDATA%\LapCoachLogger\logs\lap_coach_logger.log` | For triage |
| User config (after launch) | `%APPDATA%\LapCoachLogger\config\config.json` | Persisted settings |

## 6. Distributing RC1

1. Verify `build_info.json` — `git_dirty` must be `false`.
2. Manually test the installer on a clean Windows VM: install → launch → exit → uninstall.
3. Rename the installer to include the `-rc1` tag:
   ```bat
   rename LapCoachLogger-Setup-2.0.0.exe LapCoachLogger-Setup-2.0.0-rc1.exe
   ```
4. Upload to the RC distribution channel (internal only — RC is not code-signed, AV may flag it).
5. File a tracking issue with the build_info.json contents pasted in.

## 7. Rollback

RC1 does not auto-update, so rollback means "tell testers to uninstall and reinstall the prior build".

If a defect is found post-distribution:

1. Identify the prior green installer in artifact storage.
2. Post the prior installer URL in the release channel.
3. Testers: **Settings → Apps → Lap Coach Logger → Uninstall**, then run the prior installer.
4. User config under `%APPDATA%\LapCoachLogger\` is preserved across uninstall — no data loss.
5. File a post-mortem referencing the `build_info.json` `git_sha` of the broken build.

## 8. Known limitations / deferred to GA

- **Unsigned binary.** Windows SmartScreen will warn on first launch. Testers must click "Run anyway". *Deferred to GA: EV cert code signing.*
- **No auto-updater.** Each RC is a fresh install. *Deferred to GA.*
- **No CI-published artifact.** GitHub Actions (`.github/workflows/ci.yml`) builds on tag push but does not yet publish the installer — only the frozen folder. See `ci.yml:30-53`. *Deferred to GA.*
- **No lockfile enforcement.** `pip install -e ".[build,dev]"` resolves dep ranges live. The build captures a `pip_freeze_sha256_16` field in `build_info.json` for post-hoc drift detection, but does not reject mismatched envs. *Deferred to GA: full `requirements-lock.txt` or `uv lock` integration.*
- **PyInstaller bundle size is ~150 MB** (PySide6 brings in Qt6 DLLs + pyarrow). UPX is intentionally disabled for reproducibility and AV compatibility.
- **Demo Mode is bundled** (per recent feature work). If you need a "no demo" build, trim `src/lap_coach_logger/demo/` from the spec's `datas` — currently a known limitation, not a supported config.
- **No signed checksums.** `.sha256` + GPG signatures alongside the installer are *deferred to GA*.
- **No crash reporter.** Anonymised traceback collection is *deferred to GA*.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERROR: RC1 builds require Python 3.12.x exactly` | Wrong Python on PATH or in venv | Install 3.12, activate its venv, re-run |
| `ERROR: Inno Setup compiler not found` | ISCC.exe not installed | Install Inno Setup 6 from jrsoftware.org/isinfo.php |
| `ERROR: assets\icon.ico is required for packaging` | Icon missing from `assets\` | Restore from git; file is tracked |
| Tests fail on `test_desktop_workspaces` etc. | Qt mock pollution | The script already excludes these — if you hit it, you're running raw `pytest`, not the script |
| Smoke check timeout | App crashed on startup | Read the captured log lines; likely a bundle issue — rebuild with `--clean` |
| `git_dirty=true` in build_info | Uncommitted local changes | Commit first, then rebuild (or accept as an emergency patch) |

