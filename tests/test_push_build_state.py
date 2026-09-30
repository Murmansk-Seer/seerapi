from __future__ import annotations

from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/push_build_state.py'


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ['git', '-C', str(directory), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_file(directory: Path, name: str, contents: str, message: str) -> None:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding='utf-8')
    git(directory, 'add', name)
    git(directory, 'commit', '-m', message)


def prepare_repositories(tmp_path: Path) -> tuple[Path, Path, Path]:
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(remote))
    builder = tmp_path / 'builder'
    git(tmp_path, 'clone', str(remote), str(builder))
    git(builder, 'config', 'user.email', 'test@example.com')
    git(builder, 'config', 'user.name', 'Test')
    commit_file(builder, '.build-state/api-data-sha256', 'old\n', 'Initial state')
    git(builder, 'push', 'origin', 'main')
    author = tmp_path / 'author'
    git(tmp_path, 'clone', str(remote), str(author))
    git(author, 'config', 'user.email', 'test@example.com')
    git(author, 'config', 'user.name', 'Test')
    commit_file(builder, '.build-state/api-data-sha256', 'new\n', 'Record state')
    return remote, builder, author


def test_push_rebases_over_unrelated_remote_commit(tmp_path: Path) -> None:
    remote, builder, author = prepare_repositories(tmp_path)
    commit_file(author, 'README.md', 'new code\n', 'Advance main')
    git(author, 'push', 'origin', 'main')

    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=builder, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert git(builder, 'show', 'origin/main:.build-state/api-data-sha256') == 'new'
    assert git(builder, 'show', 'origin/main:README.md') == 'new code'
    assert git(remote, 'rev-parse', 'main') == git(builder, 'rev-parse', 'HEAD')


def test_push_refuses_concurrent_state_update(tmp_path: Path) -> None:
    remote, builder, author = prepare_repositories(tmp_path)
    commit_file(author, '.build-state/api-data-sha256', 'different\n', 'Other state')
    git(author, 'push', 'origin', 'main')

    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=builder, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert 'Remote build state changed' in result.stderr
    assert git(remote, 'show', 'main:.build-state/api-data-sha256') == 'different'
