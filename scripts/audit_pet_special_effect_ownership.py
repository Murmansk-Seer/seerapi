"""Replay effect ownership on a copy and report every changed association."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)


def _rows(connection: sqlite3.Connection, table: str) -> list[dict]:
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    names = [field[0] for field in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def _business_fingerprint(connection: sqlite3.Connection) -> str:
    digest = sha256()
    for (table,) in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ):
        if table.startswith(('sqlite_', 'pet_special_effect')):
            continue
        digest.update(table.encode())
        columns = [
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
        ]
        if table.startswith('pet_soulmark_display'):
            columns = [name for name in columns if name != 'updated_at']
        projection = ','.join(f'"{name}"' for name in columns)
        for row in connection.execute(
            f'SELECT {projection} FROM "{table}" ORDER BY rowid'
        ):
            digest.update(repr(tuple(row)).encode())
    return digest.hexdigest()


def audit(database: Path, output: Path) -> dict:
    database = database.resolve(strict=True)
    output = output.resolve()
    candidate = output / 'effect-ownership-replay.sqlite'
    if candidate == database or any(
        (output / name).exists()
        for name in (
            candidate.name,
            'audit.json',
            'audit.md',
        )
    ):
        raise FileExistsError('Replay requires a new database path')
    output.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source,
        sqlite3.connect(candidate) as replay,
    ):
        source.execute('PRAGMA query_only=ON')
        before = _rows(source, 'pet_special_effect')
        sources = _rows(source, 'pet_special_effect_source')
        pet_names = dict(source.execute('SELECT id,name FROM pet'))
        fingerprint = _business_fingerprint(source)
        source.backup(replay)
        replace_pet_special_effect_facts(replay, now=0)
        replay.commit()
        assert replay.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert _business_fingerprint(replay) == fingerprint, 'Business data changed'
        after = _rows(replay, 'pet_special_effect')
        after_sources = _rows(replay, 'pet_special_effect_source')
        issues = _rows(replay, 'pet_special_effect_issue')
        # A second build must produce identical identities and provenance.
        replace_pet_special_effect_facts(replay, now=0)
        assert after == _rows(replay, 'pet_special_effect')
        assert after_sources == _rows(replay, 'pet_special_effect_source')
        assert issues == _rows(replay, 'pet_special_effect_issue')

    def key(row):
        return row['pet_id'], row['effect_key']

    previous = {key(row): row for row in before}
    current = {key(row): row for row in after}
    sources_by_key: dict[tuple, list[dict]] = {}
    for row in sources:
        sources_by_key.setdefault(key(row), []).append(row)
    issues_by_pet: dict[int, list[dict]] = {}
    for row in issues:
        issues_by_pet.setdefault(row['pet_id'], []).append(row)

    def entry(row):
        identity = key(row)
        return {
            'pet_id': row['pet_id'],
            'pet_name': pet_names.get(row['pet_id']),
            'effect_key': row['effect_key'],
            'effect_name': row['name'],
            'before': row,
            'after': current.get(identity),
            'original_sources': sources_by_key.get(identity, []),
            'diagnostics': [
                issue
                for issue in issues_by_pet.get(row['pet_id'], [])
                if issue['effect_name'] == row['name']
            ],
        }

    weak = [
        entry(row)
        for row in before
        if row['primary_rule'] in ('text_exact_name', 'effect_description_skill_name')
    ]
    removed = [
        entry(row) for identity, row in previous.items() if identity not in current
    ]
    direct = {
        key(row)
        for row in sources
        if row['resolution_rule']
        in ('direct_pet_glossary', 'direct_status_show_monster')
    }
    assert direct <= current.keys(), 'Lost an official direct association'
    report = {
        'source_sha256': sha256(database.read_bytes()).hexdigest(),
        'business_fingerprint': fingerprint,
        'before_count': len(before),
        'after_count': len(after),
        'weak_count': len(weak),
        'weak_effect_names': sorted({row['effect_name'] for row in weak}),
        'weak_retained': sum(row['after'] is not None for row in weak),
        'removed_count': len(removed),
        'diagnostic_count': len(issues),
        'added': [row for identity, row in current.items() if identity not in previous],
        'weak_associations': weak,
        'removed_associations': removed,
        'after_facts': after,
        'after_sources': after_sources,
    }
    (output / 'audit.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8'
    )
    lines = [
        '# Effect ownership replay',
        '',
        f'Source SHA256: `{report["source_sha256"]}`',
        '',
        f'Facts: {len(before)} -> {len(after)}; removed: {len(removed)}.',
        f'Weak roots: {len(weak)}; retained with evidence: {report["weak_retained"]}.',
        '',
        '| Pet | Effect | Decision | New evidence / rejection |',
        '| --- | --- | --- | --- |',
    ]
    for row in weak:
        result = row['after']
        reasons = (
            result['primary_rule']
            if result
            else ', '.join(sorted({issue['reason'] for issue in row['diagnostics']}))
            or 'No verified ownership'
        )
        lines.append(
            f'| {row["pet_id"]} {row["pet_name"]} | {row["effect_name"]} | '
            f'{"Retained" if result else "Excluded"} | {reasons} |'
        )
    (output / 'audit.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    return {
        name: value
        for name, value in report.items()
        if name
        not in (
            'weak_associations',
            'removed_associations',
            'after_facts',
            'after_sources',
        )
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument(
        '--output', type=Path, default=Path('.cache/effect-ownership-audit')
    )
    args = parser.parse_args()
    print(json.dumps(audit(args.database, args.output), ensure_ascii=False, indent=2))  # noqa: T201
