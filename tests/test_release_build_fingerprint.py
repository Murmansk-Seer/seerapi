from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_build_fingerprint import build_fingerprint


def test_generator_change_rebuilds_without_external_data_change(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)

    git('init')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    generator = scripts / 'release_config_tables.py'
    generator.write_text('schema = 1\n')
    git('add', 'scripts')
    git('commit', '-m', 'initial generator')
    before = build_fingerprint(tmp_path)
    state = tmp_path / '.build-state'
    state.mkdir()
    (state / 'generator-fingerprint').write_text(before)
    git('add', '.build-state')
    git('commit', '-m', 'publish state')
    assert build_fingerprint(tmp_path) == before
    generator.write_text('schema = 2\n')
    git('add', 'scripts')
    git('commit', '-m', 'new schema with unchanged external data')
    assert build_fingerprint(tmp_path) != before
