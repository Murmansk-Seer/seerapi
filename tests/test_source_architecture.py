"""Source-level architecture limits for maintained Python modules."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    ROOT / 'scripts',
    ROOT / 'packages' / 'solaris' / 'solaris',
    ROOT / 'packages' / 'seerapi-models' / 'seerapi_models',
    ROOT / 'packages' / 'seerapi-python' / 'seerapi',
)
MAX_MAINTAINED_MODULE_LINES = 800
GENERATED_MODULES = frozenset(
    {
        ROOT
        / 'packages'
        / 'solaris'
        / 'solaris'
        / 'analyze'
        / 'output'
        / 'openapi_comments.py',
    }
)


def test_maintained_python_modules_stay_below_size_limit() -> None:
    oversized = []
    for source_root in SOURCE_ROOTS:
        for path in source_root.rglob('*.py'):
            if path in GENERATED_MODULES:
                continue
            line_count = len(path.read_text(encoding='utf-8').splitlines())
            if line_count > MAX_MAINTAINED_MODULE_LINES:
                oversized.append(
                    f'{path.relative_to(ROOT)}: {line_count} lines'
                )
    assert not oversized, 'Oversized maintained modules:\n' + '\n'.join(oversized)
