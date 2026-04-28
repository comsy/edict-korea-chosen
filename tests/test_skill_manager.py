"""tests for scripts/skill_manager.py"""
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "skill_manager.py"


def test_skill_manager_help_is_korean():
    """Skill manager help output should be Korean-first for users."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert "Skill 관리 도구" in output
    assert "원격 skill 추가" in output
    assert "三省六部" not in output
    assert "从远程 URL 添加 skill" not in output
