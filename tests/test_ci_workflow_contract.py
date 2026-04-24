"""Regression test: CI workflow runs pytest on pull_request (sprint T015).

Blocks merge when pytest fails by asserting the workflow at
``.github/workflows/ci.yml`` triggers on ``pull_request`` against
``master`` and invokes ``pytest -q`` — the conditions GitHub's branch
protection relies on to require the job passing.
"""
from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CI_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_workflow() -> dict:
    return yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))


def _all_run_steps(job: dict) -> list[str]:
    return [
        step["run"]
        for step in job.get("steps", []) or []
        if isinstance(step, dict) and isinstance(step.get("run"), str)
    ]


def test_workflow_file_exists() -> None:
    assert CI_PATH.exists(), (
        f".github/workflows/ci.yml missing — T015 requires a CI workflow"
    )


def test_workflow_triggers_on_pull_request_to_master() -> None:
    wf = _load_workflow()
    # PyYAML parses the YAML key ``on`` as the Python boolean True, so try both.
    triggers = wf.get("on", wf.get(True))
    assert triggers is not None, "workflow has no triggers"
    pr = triggers.get("pull_request")
    assert pr is not None, "workflow does not trigger on pull_request"
    assert "master" in pr.get("branches", []), (
        "pull_request trigger does not cover master"
    )


def test_workflow_invokes_pytest_in_test_job() -> None:
    wf = _load_workflow()
    test_job = wf["jobs"]["test"]
    run_commands = "\n".join(_all_run_steps(test_job))
    assert "pytest" in run_commands, "test job has no pytest step"
    assert "-q" in run_commands, "pytest step missing quiet flag"


def test_workflow_test_job_runs_on_supported_runner() -> None:
    wf = _load_workflow()
    runner = wf["jobs"]["test"]["runs-on"]
    # Windows desktop app — CI must run on a Windows runner.
    assert "windows" in runner.lower(), (
        f"test job runner is {runner!r}; Windows app needs a Windows runner"
    )
