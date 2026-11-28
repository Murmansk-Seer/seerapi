"""Replay a frozen official client configuration into a new local candidate DB."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import md5, sha256
import json
from pathlib import Path
import sqlite3

from solaris.analyze.output.pet_effect_visibility import status_container_decisions
from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)
from solaris.analyze.output.pet_special_effect_resolution import (
    collect_pet_special_effect_facts,
)

if __package__:
    from .build_http import extract_text_assets
    from .client_effect_sources import (
        CLIENT_EFFECT_ASSETS,
        parse_client_effect_data,
        replace_client_effect_tables,
    )
    from .item_exchange_sources import ItemExchangePrice
    from .release_contract import (
        SCHEMA_CONTRACT_VERSION,
        SCHEMA_CONTRACT_VERSION_KEY,
        finalize_release_contract,
    )
    from .release_reference_tables import replace_reference_tables
    from .render_asset_manifest_build import render_asset_manifest_revision
    from .render_asset_manifest_types import RenderAssetManifestEntry
else:
    from build_http import extract_text_assets
    from client_effect_sources import (
        CLIENT_EFFECT_ASSETS,
        parse_client_effect_data,
        replace_client_effect_tables,
    )
    from item_exchange_sources import ItemExchangePrice
    from release_contract import (
        SCHEMA_CONTRACT_VERSION,
        SCHEMA_CONTRACT_VERSION_KEY,
        finalize_release_contract,
    )
    from release_reference_tables import replace_reference_tables
    from render_asset_manifest_build import render_asset_manifest_revision
    from render_asset_manifest_types import RenderAssetManifestEntry

DERIVED = {
    'pet_special_effect',
    'pet_special_effect_icon',
    'pet_special_effect_source',
    'pet_special_effect_issue',
    'pet_soulmark_display',
    'pet_soulmark_display_addition',
    'seerapi_metadata',
    'render_asset_manifest',
    'effect_description',
    'special_effect_status',
    'special_effect_status_variant',
}


def business_snapshot(c: sqlite3.Connection) -> dict[str, str]:
    result = {}
    for (table,) in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        if table in DERIVED:
            continue
        columns = [
            r[1]
            for r in c.execute(f'PRAGMA table_info("{table}")')
            if r[1] != 'updated_at'
        ]
        expression = ','.join('"' + name + '"' for name in columns)
        rows = [
            repr(tuple(row)) for row in c.execute(f'SELECT {expression} FROM "{table}"')
        ]
        result[table] = sha256('\n'.join(sorted(rows)).encode()).hexdigest()
    return result


def facts(c: sqlite3.Connection) -> list[dict]:
    c.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in c.execute(
            'SELECT * FROM pet_special_effect ORDER BY pet_id,effect_key'
        )
    ]
    c.row_factory = None
    if c.execute(
        "SELECT 1 FROM sqlite_master WHERE name='pet_special_effect_icon'"
    ).fetchone():
        icons: dict[tuple[int, str], list[tuple[str, str, int | None, int | None]]] = {}
        for pet_id, key, *icon in c.execute(
            'SELECT pet_id,effect_key,icon_kind,icon_asset_key,status_id,variant_value '
            'FROM pet_special_effect_icon ORDER BY pet_id,effect_key,icon_kind,icon_asset_key'
        ):
            icons.setdefault((pet_id, key), []).append(
                (icon[0], icon[1], icon[2], icon[3])
            )
        for row in rows:
            row['icons'] = icons.get((row['pet_id'], row['effect_key']), [])
    return rows


def audit(source: Path, bundle: Path, provenance: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    source_hash = sha256(source.read_bytes()).hexdigest()
    evidence = json.loads(provenance.read_text(encoding='utf-8'))
    raw = bundle.read_bytes()
    if (
        md5(raw).hexdigest() != evidence['bundle_md5']
        or sha256(raw).hexdigest() != evidence['bundle_sha256']
    ):
        raise ValueError('Frozen official bundle digest mismatch')
    assets = extract_text_assets(raw, CLIENT_EFFECT_ASSETS)
    data = parse_client_effect_data(assets, evidence['version'])
    with sqlite3.connect(
        'file:' + source.resolve().as_posix() + '?mode=ro', uri=True
    ) as original:
        version = original.execute(
            'SELECT data_version FROM api_metadata LIMIT 1'
        ).fetchone()[0]
        if version != data.config_version:
            raise ValueError(
                f'Configuration/release version mismatch: {version} != {data.config_version}'
            )
        before = facts(original)
        before_sources = {}
        for pet_id, key, kind, rule in original.execute(
            'SELECT pet_id,effect_key,source_kind,resolution_rule FROM pet_special_effect_source'
        ):
            before_sources.setdefault((pet_id, key), []).append(
                {'source_kind': kind, 'resolution_rule': rule}
            )
        business = business_snapshot(original)
        output.mkdir(parents=True)
        candidate = output / 'seerapi-data.sqlite'
        with sqlite3.connect(candidate) as c:
            original.backup(c)
            c.row_factory = sqlite3.Row
            prices = [
                ItemExchangePrice(
                    **{key: r[key] for key in r.keys() if key != 'updated_at'}
                )
                for r in c.execute('SELECT * FROM item_exchange_price')
            ]
            c.row_factory = None
            replace_reference_tables(
                c,
                item_exchange_prices=prices,
                effect_descriptions=data.descriptions,
                special_effect_statuses=data.statuses,
                now=0,
            )
            replace_client_effect_tables(c, data)
            # Existing immutable abnormal blobs are reusable under the explicit
            # glossary namespace; missing blobs stay absent, never fabricated.
            c.execute(
                "INSERT OR IGNORE INTO render_asset_manifest SELECT 'abnormal',asset_key,sha256,release_revision,available,source,updated_at FROM render_asset_manifest WHERE asset_kind='battle_effect'"
            )
            entries = tuple(
                RenderAssetManifestEntry(*row)
                for row in c.execute(
                    'SELECT asset_kind,asset_key,sha256,release_revision,available,source FROM render_asset_manifest ORDER BY asset_kind,asset_key'
                )
            )
            c.executemany(
                'INSERT OR REPLACE INTO seerapi_metadata(key,value) VALUES (?,?)',
                [
                    (
                        'render_asset_manifest_revision',
                        render_asset_manifest_revision(entries),
                    ),
                    ('render_asset_manifest_count', str(len(entries))),
                    (
                        'render_asset_manifest_available_count',
                        str(sum(e.available for e in entries)),
                    ),
                    ('pet_effect_association_contract', '3'),
                    (SCHEMA_CONTRACT_VERSION_KEY, SCHEMA_CONTRACT_VERSION),
                ],
            )
            summary = replace_pet_special_effect_facts(c, now=0)
            after = facts(c)
            collected, _ = collect_pet_special_effect_facts(c)
            display_decisions = [
                asdict(d) for d in status_container_decisions(c, collected)
            ]
            observed = business_snapshot(c)
            assert all(
                observed[table] == digest for table, digest in business.items()
            ), 'Unrelated business data changed'
            first = [
                tuple(row)
                for row in c.execute(
                    'SELECT * FROM pet_special_effect_source ORDER BY pet_id,effect_key,source_kind,source_id,resolution_rule'
                )
            ]
            replace_pet_special_effect_facts(c, now=0)
            assert after == facts(c)
            assert first == [
                tuple(row)
                for row in c.execute(
                    'SELECT * FROM pet_special_effect_source ORDER BY pet_id,effect_key,source_kind,source_id,resolution_rule'
                )
            ]
            issues = [
                dict(
                    zip(
                        ('pet_id', 'effect_name', 'candidate_id', 'reason', 'context'),
                        row,
                    )
                )
                for row in c.execute(
                    'SELECT pet_id,effect_name,candidate_id,reason,context FROM pet_special_effect_issue ORDER BY pet_id,effect_name,candidate_id,reason'
                )
            ]
            panel_sources = [
                dict(zip(('pet_id', 'effect_key', 'panel_id', 'detail'), row))
                for row in c.execute(
                    "SELECT pet_id,effect_key,source_id,source_detail FROM pet_special_effect_source WHERE source_kind='pet_effect_panel' ORDER BY pet_id,effect_key,source_id"
                )
            ]
            c.commit()
    finalize_release_contract(candidate)
    assert sha256(source.read_bytes()).hexdigest() == source_hash
    digest = sha256(candidate.read_bytes()).hexdigest()
    (output / 'seerapi-data.sqlite.sha256').write_text(
        f'{digest}  seerapi-data.sqlite\n', encoding='ascii'
    )
    before_keys = {(r['pet_id'], r['effect_key']) for r in before}
    after_keys = {(r['pet_id'], r['effect_key']) for r in after}
    after_by_key = {(r['pet_id'], r['effect_key']): r for r in after}
    retired_icons = []
    for old in before:
        new = after_by_key.get((old['pet_id'], old['effect_key']))
        if (
            old['status_id'] is not None or old.get('icon_key') or old.get('icons')
        ) and (new is None or not new['icons']):
            retired_icons.append(
                {
                    'pet_id': old['pet_id'],
                    'effect_key': old['effect_key'],
                    'name': old['name'],
                    'old_status_id': old['status_id'],
                    'old_icon_key': old.get('icon_key'),
                    'text_fact_retained': new is not None,
                    'old_sources': before_sources.get(
                        (old['pet_id'], old['effect_key']), []
                    ),
                    'reason': 'No verified client ID, panel heading or conditional display reference establishes this icon identity; retain unresolved evidence rather than guess.',
                }
            )
    report = {
        'source_sha256': source_hash,
        'candidate_sha256': digest,
        'config': evidence,
        'summary': asdict(summary),
        'before': before,
        'after': after,
        'state_container_display': display_decisions,
        'new_facts': [
            r for r in after if (r['pet_id'], r['effect_key']) not in before_keys
        ],
        'removed_facts': [
            r for r in before if (r['pet_id'], r['effect_key']) not in after_keys
        ],
        'retired_icon_bindings': retired_icons,
        'panel_sources': panel_sources,
        'issues': issues,
        'business_unchanged': True,
        'deterministic': True,
        'local_only': True,
    }
    (output / 'audit.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    lines = [
        '# Client effect association replay',
        '',
        f'- Official configuration: `{version}`',
        f'- Source SHA256: `{source_hash}`',
        f'- Candidate SHA256: `{digest}`',
        f'- Facts: {len(before)} -> {len(after)}',
        f'- New fact identities: {len(report["new_facts"])}',
        f'- Removed fact identities: {len(report["removed_facts"])}',
        f'- Panel evidence rows: {len(panel_sources)}',
        f'- Hidden state containers: {sum(not d["display_in_pet_info"] for d in display_decisions)}',
        '- Unrelated business tables unchanged; deterministic replay passed.',
        '- This candidate is local only, not a production release.',
        '',
        'Full per-fact sources, removed bindings and issues are in audit.json.',
    ]
    (output / 'audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--provenance', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.source, args.bundle, args.provenance, args.output)
    print(  # noqa: T201 - CLI output
        json.dumps(
            {
                k: report[k]
                for k in (
                    'source_sha256',
                    'candidate_sha256',
                    'summary',
                    'business_unchanged',
                    'deterministic',
                )
            },
            indent=2,
        )
    )


if __name__ == '__main__':
    main()
