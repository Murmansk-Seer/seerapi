import json
import logging
from pathlib import Path
import sqlite3
import struct
import sys
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from autocard_sources import (
    AutocardData,
    json_data_rows,
    normalize_autocard_row,
    parse_autocard_json,
)
from release_autocard_tables import replace_autocard_tables
from release_contract import validate_autocard_source
from release_source_loaders import ReleaseSourceConfig, ReleaseSourceLoader


def _card_bytes() -> bytes:
    values = (
        '10028|10337',
        '1|7_7_1_1',
        0,
        0,
        1,
        2,
        '新的效果',
        0,
        10208,
        3,
        '',
        1,
        4,
        208,
        1,
        4,
        '麦索瑞尔',
        7,
        1,
        '',
        0,
        1,
    )
    data = bytearray(b'\x01' + struct.pack('<i', 1))
    for value in values:
        if isinstance(value, str):
            text = value.encode('utf-8')
            data.extend(struct.pack('<H', len(text)))
            data.extend(text)
        else:
            data.extend(struct.pack('<i', value))
    return bytes(data)


def _loader() -> ReleaseSourceLoader:
    config = cast(
        ReleaseSourceConfig,
        SimpleNamespace(
            autocard_json_dir='',
            autocard_json_base_url='https://stale.invalid/json/',
        ),
    )
    return ReleaseSourceLoader(Mock(), config, logger=logging.getLogger(__name__))


def test_autocard_uses_same_verified_bundle_not_stale_json():
    loader = _loader()
    loader._autocard_assets = {'autocardContent.bytes': _card_bytes()}
    loader._autocard_source = (
        'https://official.invalid/hash?config_version=20261029221429'
    )
    raw, source = loader.load_autocard_json('autocardContent.json')
    rows = json_data_rows(raw)
    assert rows[0]['BuffId'] == '10028|10337'
    assert rows[0]['BuffParam'] == '1|7_7_1_1'
    assert rows[0]['cardTxt'] == '新的效果'
    assert source.endswith('20261029221429#autocardContent.bytes')
    cast(Mock, loader._http.download_bytes).assert_not_called()


def test_missing_or_disabled_official_source_never_falls_back():
    loader = _loader()
    with pytest.raises(ValueError, match='verified ConfigPackage'):
        loader.load_autocard_json('autocardContent.json')
    loader._autocard_assets = {}
    with pytest.raises(KeyError):
        loader.load_autocard_json('autocardContent.json')
    loader._autocard_assets = {'autocardContent.bytes': b'\x00'}
    with pytest.raises(ValueError, match='empty'):
        loader.load_autocard_json('autocardContent.json')
    cast(Mock, loader._http.download_bytes).assert_not_called()


@pytest.mark.parametrize(
    'filename',
    [
        'autocardContent.json',
        'autocardRole.json',
        'autocardNature.json',
        'autocardBuff.json',
    ],
)
def test_disabled_tables_are_not_a_success(filename):
    with pytest.raises(ValueError, match='empty'):
        parse_autocard_json(filename, b'\x00')


def test_field_names_keep_the_existing_raw_contract():
    assert normalize_autocard_row(
        {'buff_id': '1', 'card_txt': 'effect', 'pic_id': 2}
    ) == {
        'BuffId': '1',
        'cardTxt': 'effect',
        'picID': 2,
    }
    assert normalize_autocard_row(
        {'buff_param': 'a'}, filename='autocardBuff.json'
    ) == {'buffParam': 'a'}
    with pytest.raises(ValueError, match='conflicting'):
        normalize_autocard_row({'buff_id': '1', 'BuffId': '2'})


def test_full_publication_gate_catches_stale_sidecars_and_accepts_aliases(tmp_path):
    raw = {
        'autocardContent.json': {
            'id': 208,
            'name': '麦索瑞尔',
            'buff_param': '1|7_7_1_1',
        },
        'autocardRole.json': {
            'id': 1,
            'name': 'role',
            'nature': 1,
            'skill_txt': 'current',
        },
        'autocardNature.json': {'id': 1, 'name': '草', 'pic_id': 'grass'},
        'autocardBuff.json': {
            'id': 10337,
            'buff_object': '卡牌',
            'buff_param': 'a_b',
            'buff_des': 'effect',
        },
    }
    normalized = {
        key: normalize_autocard_row(row, filename=key) for key, row in raw.items()
    }
    unity = tmp_path / 'unity'
    unity.mkdir()
    for name, row in raw.items():
        (unity / name).write_text(json.dumps({'data': [row]}), encoding='utf-8')
    with sqlite3.connect(':memory:') as conn:
        replace_autocard_tables(
            conn,
            AutocardData(
                cards=[normalized['autocardContent.json']],
                roles=[normalized['autocardRole.json']],
                natures=[normalized['autocardNature.json']],
                buffs=[normalized['autocardBuff.json']],
                source='official ConfigPackage',
            ),
            0,
        )
        validate_autocard_source(conn, tmp_path)
        assert conn.execute(
            'SELECT object,param,param_description FROM autocard_buff'
        ).fetchone() == ('卡牌', 'a_b', 'effect')
        conn.execute(
            'UPDATE autocard_card SET raw_json=? WHERE id=208',
            (json.dumps({'id': 208, 'name': '麦索瑞尔', 'BuffParam': '1|7_2_1'}),),
        )
        with pytest.raises(ValueError, match='autocard_card differs'):
            validate_autocard_source(conn, tmp_path)
