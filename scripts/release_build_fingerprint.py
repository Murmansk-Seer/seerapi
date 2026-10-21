"""Fingerprint committed database-generator inputs, excluding build state."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess


def build_fingerprint(repository: Path) -> str:
    tree = subprocess.check_output(
        ['git', 'ls-tree', '-r', 'HEAD', '--', 'scripts', 'packages',
         'pyproject.toml', 'uv.lock', '.github/workflows/build-seerapi-data-db.yml'],
        cwd=repository,
    )
    return sha256(tree).hexdigest()


if __name__ == '__main__':
    print(build_fingerprint(Path.cwd()))  # noqa: T201
