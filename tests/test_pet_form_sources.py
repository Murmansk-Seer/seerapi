from __future__ import annotations

from pathlib import Path
import sqlite3
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pet_form_sources import (
    PetFormMember,
    PetFormResource,
    parse_pet_form_members,
    parse_pet_form_resources,
    replace_pet_form_tables,
)


def _int(value: int) -> bytes:
    return struct.pack('<i', value)


def _text(value: str) -> bytes:
    encoded = value.encode()
    return struct.pack('<H', len(encoded)) + encoded


def test_parse_official_poly_layout_preserves_form_positions() -> None:
    binary = (
        b'\1'
        + _int(2)
        + _int(1)
        + _int(4950)
        + _text('290004950')
        + _int(0)
        + _int(2)
        + _int(0)
        + _text('2900871;0;2900873')
        + _int(871)
    )
    assert parse_pet_form_resources(binary) == [
        PetFormResource(4950, 0, 1, 290004950),
        PetFormResource(0, 871, 1, 2900871),
        PetFormResource(0, 871, 3, 2900873),
    ]
    with pytest.raises(ValueError, match='trailing'):
        parse_pet_form_resources(binary + b'\0')
    with pytest.raises((ValueError, struct.error, IndexError)):
        parse_pet_form_resources(binary[:-2])


def test_parse_official_composition_and_publish_sqlite() -> None:
    binary = (
        b'\1'
        + _int(1)
        + _text('activate')
        + b'\1'
        + _int(2)
        + _int(3311)
        + _int(13311)
        + _text('change')
        + _text('description')
        + _int(3311)
        + _int(400230)
    )
    members = parse_pet_form_members(binary)
    assert members == [PetFormMember(3311, 3311), PetFormMember(3311, 13311)]
    with sqlite3.connect(':memory:') as conn:
        replace_pet_form_tables(conn, [PetFormResource(0, 871, 1, 2900871)], members)
        assert conn.execute('SELECT * FROM pet_form_resource').fetchall() == [
            (0, 871, 1, 2900871)
        ]
        assert conn.execute('SELECT * FROM pet_form_member').fetchall() == [
            (3311, 3311),
            (3311, 13311),
        ]
        replace_pet_form_tables(conn, [], [])
        assert conn.execute('SELECT COUNT(*) FROM pet_form_resource').fetchone() == (0,)


def test_absent_tables_are_empty_only_when_officially_encoded_empty() -> None:
    assert parse_pet_form_resources(b'\0') == []
    assert parse_pet_form_members(b'\0') == []
    with pytest.raises(IndexError):
        parse_pet_form_resources(b'')


def test_form_images_are_included_in_release_manifest() -> None:
    from build_seerapi_data_db import RENDER_ASSET_MANIFEST_CONFIG
    from render_asset_manifest_build import _build_pet_form_manifest
    from render_asset_repository import AssetRepositorySnapshot

    prefix = 'newseer/assets/art/ui/assets/pet'
    snapshot = AssetRepositorySnapshot(
        revision='a' * 40,
        blobs_by_path={
            f'{prefix}/{kind}/2900871.png': 'b' * 40 for kind in ('head', 'body')
        },
    )
    with sqlite3.connect(':memory:') as conn:
        replace_pet_form_tables(conn, [PetFormResource(0, 871, 1, 2900871)], [])
        entries = _build_pet_form_manifest(
            conn,
            {'default': snapshot},
            release_revision='test',
            config=RENDER_ASSET_MANIFEST_CONFIG,
        )
        assert {
            (entry.asset_kind, entry.asset_key, entry.available) for entry in entries
        } == {
            ('pet_head', '2900871', True),
            ('pet_body', '2900871', True),
        }
