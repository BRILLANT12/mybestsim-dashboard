"""Garde-fous sur le workflow GitHub Actions (lecture du fichier, sans dépendance YAML)."""

import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/dashboard.yml").read_text(encoding="utf-8")


def test_triggers_push_on_data_daily_cron_and_manual():
    block = re.search(r"on:\n  push:\n    branches: \[main\]\n    paths:\n((?:      - .+\n)+)", WORKFLOW)
    assert block, "déclencheur push introuvable"
    paths = re.findall(r'- "([^"]+)"', block.group(1))
    assert paths == ["data/**", "dashboard/**", "docs/**", ".github/workflows/dashboard.yml"]
    assert re.search(r"schedule:\n\s+# .*\n\s+- cron: \"\d+ \d+ \* \* \*\"", WORKFLOW)
    assert "\n  workflow_dispatch:\n" in WORKFLOW


def test_every_action_is_pinned_to_a_full_commit_sha():
    uses = re.findall(r"uses: ([^\s]+)", WORKFLOW)
    assert len(uses) == 6
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), f"action non figée : {ref}"


def test_least_privilege_permissions():
    head = WORKFLOW.split("jobs:")[0]
    assert "permissions:\n  contents: read\n" in head
    assert WORKFLOW.count("pages: write") == 1 and WORKFLOW.count("id-token: write") == 1
    assert "contents: write" not in WORKFLOW and "persist-credentials: false" in WORKFLOW


def test_tests_run_with_node_and_chrome_before_generation_and_publication():
    order = [WORKFLOW.index(step) for step in ("node --version", "google-chrome --version", "python -m pytest -q",
                                                  "python -m dashboard", "upload-pages-artifact", "deploy-pages")]
    assert order == sorted(order)
    assert 'python-version: "3.12"' in WORKFLOW and "path: docs" in WORKFLOW
    assert "needs: build" in WORKFLOW
