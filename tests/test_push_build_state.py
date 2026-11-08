from pathlib import Path
import subprocess
import sys


def test_retired_main_writer_refuses_to_publish(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / 'scripts/push_build_state.py'
    result = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert 'pipeline-state action' in result.stderr
    assert not (tmp_path / '.git').exists()
