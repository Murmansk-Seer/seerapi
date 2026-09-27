from __future__ import annotations

from pathlib import Path
import sqlite3
import struct
import sys

SCRIPT_DIRECTORY = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

import backfill_autocard_chip_baseline as baseline
from build_new_content_index import build_release_state, write_release_state
from config_package_sources import (
    AutocardChip,
    BundleInfo,
    PackageManifestData,
    parse_autocard_chips,
)
from release_autocard_tables import replace_autocard_chip_table
from test_build_new_content_index import _create_database as _create_base_database


def _text(value: str) -> bytes:
    raw = value.encode('utf-8')
    return struct.pack('<H', len(raw)) + raw


def _payload(heal: int) -> bytes:
    description = f'己方所有精灵恢复{heal}点生命值'
    return (
        struct.pack('<Bi', 1, 1)
        + _text(description)
        + struct.pack('<iii', 115, 3, 1)
        + _text('复苏之风 I')
        + struct.pack('<ii', 115, 60)
        + _text('防御/续航类')
    )


def _database(path: Path, version: str, heal: int | None) -> None:
    _create_base_database(path, version=version, pet_ids=(1,))
    with sqlite3.connect(path) as conn:
        if heal is not None:
            replace_autocard_chip_table(conn, parse_autocard_chips(_payload(heal)), 1.0)


def test_parse_and_publish_autocard_chip() -> None:
    chip = parse_autocard_chips(_payload(5))[0]
    assert chip == AutocardChip(115, '复苏之风 I', '己方所有精灵恢复5点生命值', 3, 1, 115, 60, '防御/续航类')
    with sqlite3.connect(':memory:') as conn:
        replace_autocard_chip_table(conn, [chip], 1.0)
        row = conn.execute(
            'SELECT id, name, description, rarity, config_group_id, source '
            'FROM autocard_chip'
        ).fetchone()
    assert row == (115, '复苏之风 I', '己方所有精灵恢复5点生命值', 1, 60, 'ConfigPackage/autocardChip.bytes')


def test_chip_first_observation_does_not_report_all_rows(tmp_path: Path) -> None:
    old = tmp_path / 'old.sqlite'
    new = tmp_path / 'new.sqlite'
    _database(old, '20260918180640', None)
    _database(new, '20260924175611', 5)
    state = build_release_state(new, old, 'new')
    assert state.items == ()
    assert not next(row for row in state.category_states if row.category == 'autocard_chip').comparison_ready


def test_historical_chip_backfill_is_optional(
    tmp_path: Path, monkeypatch,
) -> None:
    old = tmp_path / 'old.sqlite'
    _database(old, '20260924175611', None)
    requested_urls: list[str] = []
    def download(_self, url: str) -> bytes:
        requested_urls.append(url)
        return b'bundle'
    monkeypatch.setattr(
        baseline.BuildHttpClient, 'download_bytes',
        download,
    )
    monkeypatch.setattr(
        baseline, 'parse_package_manifest',
        lambda _raw: PackageManifestData(
            bundles=(BundleInfo('pgame_configs_bytes', 'hash', 6),), assets={},
        ),
    )
    monkeypatch.setattr(
        baseline, 'extract_text_assets',
        lambda _raw, _wanted: {'autocardChip.bytes': _payload(2)},
    )
    assert baseline.backfill(old, '20260924175611')
    assert 'PackageManifest_ConfigPackage_20260918180640.bytes' in requested_urls[0]
    with sqlite3.connect(old) as conn:
        assert conn.execute('SELECT count(*) FROM autocard_chip').fetchone() == (1,)

    unavailable = tmp_path / 'unavailable.sqlite'
    _database(unavailable, '20260918180640', None)
    def fail(_self, _url):
        raise OSError('historical package unavailable')
    monkeypatch.setattr(baseline.BuildHttpClient, 'download_bytes', fail)
    assert not baseline.backfill(unavailable, '20260924175611')
    with sqlite3.connect(unavailable) as conn:
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'autocard_chip'"
        ).fetchone() is None

    assert baseline._historical_version('20261002123456', '20261003123456') is None


def test_chip_weekly_change_keeps_original_description(tmp_path: Path) -> None:
    old = tmp_path / 'old.sqlite'
    current = tmp_path / 'current.sqlite'
    rebuild = tmp_path / 'rebuild.sqlite'
    _database(old, '20260918180640', 2)
    _database(current, '20260924175611', 5)
    _database(rebuild, '20260924175611', 7)
    baseline = build_release_state(old, None, 'old')
    write_release_state(old, baseline, None)
    first = build_release_state(current, old, 'current')
    chip = next(item for item in first.items if item.category == 'autocard_chip')
    assert chip.change_kind == 'modified'
    assert chip.payload['previous_description'].endswith('2点生命值')
    write_release_state(current, first, baseline)
    second = build_release_state(rebuild, current, 'rebuild')
    chip = next(item for item in second.items if item.category == 'autocard_chip')
    assert chip.payload['previous_description'].endswith('2点生命值')
    assert chip.payload['description'].endswith('7点生命值')
