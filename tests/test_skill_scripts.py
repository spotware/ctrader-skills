"""Auto-discovered self-tests for every skill script in ``skills/*/scripts/*.py``.

Each discovered script is invoked with ``--self-test`` as a subprocess; exit code
must be 0 for the test case to pass. No conftest.py exists in this directory to
mitigate the conftest.py RCE vector.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS: list[Path] = sorted(ROOT.glob('skills/*/scripts/*.py'))


@pytest.mark.parametrize(
    'script',
    SKILL_SCRIPTS,
    ids=lambda p: f'{p.parent.parent.name}/{p.name}',
)
def test_skill_script_self_test(script: Path) -> None:
    """Run ``python <script> --self-test`` and assert exit code 0.

    Args:
        script: Path to the skill script.
    """
    result = subprocess.run(
        [sys.executable, str(script), '--self-test'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f'self-test failed for {script}:\n'
        f'  exit code: {result.returncode}\n'
        f'  stdout: {result.stdout}\n'
        f'  stderr: {result.stderr}'
    )


def test_at_least_one_script_discovered() -> None:
    """Sanity guard: at least one skill script must be discovered.

    Catches misconfiguration where the glob silently matches nothing.
    """
    assert SKILL_SCRIPTS, (
        'No skill scripts discovered via skills/*/scripts/*.py glob. '
        'Either no skill has scripts (unlikely), or the test directory '
        'location has changed and ROOT is wrong.'
    )
