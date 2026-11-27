from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import struct

import pytest
from test_pet_special_effect_facts import _connection

from scripts.client_effect_sources import ClientEffectData, replace_client_effect_tables
from scripts.effect_metadata_sources import parse_special_effect_statuses
from solaris.analyze.output.pet_effect_panels import (
    PetEffectPanel,
    panel_headings,
    replace_panel_table,
)
from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)
from solaris.analyze.output.pet_special_effect_types import (
    EffectSource,
    SpecialEffectFactAccumulator,
)
from solaris.parse.parsers.effect_des import EffectDesParser
from solaris.parse.parsers.pet_effect_icon import PetEffectIconParser
from solaris.parse.parsers.sign_icon_fight import SignIconFightParser


def heading(name: str) -> str:
    return f'<indent=0><sprite=5><indent=15>{name}：'


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        (heading('星盘（下场保留）'), '星盘'),
        (heading('神耀能量（上限6层，下场保留）'), '神耀能量'),
        (heading('算力限制'), '算力限制'),
        (heading('算力（未知条件）'), '算力（未知条件）'),
    ],
)
def test_only_complete_structured_headings(text, expected):
    assert panel_headings(text)[0][0] == expected
    assert panel_headings(text + '\n' + text) == panel_headings(text)
    assert not panel_headings('正文包含' + text)
    assert not panel_headings('<indent=16><sprite=3>谧夜之幕：')


@pytest.mark.parametrize('ambiguous', [False, True])
def test_panel_reference_is_unique_and_deterministic(ambiguous):
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    c.execute("INSERT INTO special_effect_status VALUES (10,'星盘','A',0)")
    if ambiguous:
        c.execute("INSERT INTO special_effect_status VALUES (11,'星盘','A',0)")
    replace_panel_table(
        c,
        (
            PetEffectPanel(
                20, 1, 30, heading('星盘（下场保留）'), False, '20261127104733'
            ),
        ),
    )
    for now in (1, 2):
        replace_pet_special_effect_facts(c, now=now)
        assert c.execute(
            'SELECT status_id,icon_kind,icon_key FROM pet_special_effect'
        ).fetchall() == ([] if ambiguous else [(10, 'sign_buff', '10')])
        if not ambiguous:
            source = c.execute(
                "SELECT source_kind,source_id,source_detail FROM pet_special_effect_source WHERE source_kind='pet_effect_panel'"
            ).fetchone()
            assert source[:2] == ('pet_effect_panel', 20)
            assert json.loads(source[2])['effecticonid'] == 30
        else:
            assert c.execute(
                "SELECT COUNT(*) FROM pet_special_effect_issue WHERE reason='ambiguous_panel_heading'"
            ).fetchone() == (2,)


def test_existing_different_term_is_not_fuzzy_merged_or_duplicated():
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    c.execute("INSERT INTO glossary_entry VALUES (234,'圣诰','old')")
    c.execute('INSERT INTO petglossaryentrylink VALUES (1,234)')
    c.execute("INSERT INTO special_effect_status VALUES (70,'圣告','',0)")
    c.execute("INSERT INTO effect_description VALUES (234,'圣诰','old')")
    c.execute(
        "INSERT INTO soulmark VALUES (3,'','[color=#f35555]圣诰[/color]','',0,0,NULL)"
    )
    c.execute('INSERT INTO petsoulmarklink VALUES (1,3)')
    replace_panel_table(
        c, (PetEffectPanel(2, 1, 3, heading('圣告'), False, '20261127104733'),)
    )
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT glossary_id,status_id,name FROM pet_special_effect'
    ).fetchall() == [(234, None, '圣诰')]
    assert c.execute('SELECT reason FROM pet_special_effect_issue').fetchall() == [
        ('panel_conflicting_existing_term',)
    ]


def test_panel_attaches_to_exact_existing_fact_without_duplicate():
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    c.execute("INSERT INTO glossary_entry VALUES (234,'星盘','old')")
    c.execute('INSERT INTO petglossaryentrylink VALUES (1,234)')
    c.execute("INSERT INTO special_effect_status VALUES (70,'星盘','',0)")
    replace_panel_table(
        c, (PetEffectPanel(2, 1, 3, heading('星盘'), False, '20261127104733'),)
    )
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT glossary_id,status_id FROM pet_special_effect'
    ).fetchall() == [(234, 70)]
    assert c.execute('SELECT COUNT(*) FROM pet_special_effect_source').fetchone() == (
        2,
    )


def test_distinct_explicit_ids_do_not_merge_by_identical_text():
    facts = SpecialEffectFactAccumulator()
    for status_id in (203, 219):
        facts.add(
            pet_id=1,
            name='不武',
            description='same',
            status_id=status_id,
            source=EffectSource('status', status_id, 'direct_status_show_monster'),
        )
    assert len(facts.facts) == 2
    assert {f.effect_key for f in facts.facts} == {'s:203', 's:219'}


@pytest.mark.parametrize(
    ('mapping', 'expected'), [(None, '94'), ('1_0', '94'), ('1_2', '94_2')]
)
def test_client_icon_mapping_and_display_rules(mapping, expected):
    row = {
        'id': 94,
        'dec': '星执',
        'sp_tips': ['1_麻痹'],
        'sp_icon': [] if mapping is None else [mapping],
        'show_monster': ['1_4620_0_1'],
    }
    statuses = parse_special_effect_statuses(
        json.dumps({'config': {'item': [row]}}).encode()
    )
    assert statuses[0].variants[0].icon_key == expected
    assert statuses[0].show_monster_id == 0
    c = sqlite3.connect(':memory:')
    replace_client_effect_tables(
        c, ClientEffectData((), (), [], statuses, '20261127104733')
    )
    assert c.execute(
        'SELECT raw_rule,state_value,pet_id,show_icon,show_frame FROM special_effect_status_display_rule'
    ).fetchall() == [('1_4620_0_1', 1, 4620, 0, 1)]


def test_invalid_icon_mapping_rejects_publication():
    with pytest.raises(ValueError, match='invalid literal'):
        parse_special_effect_statuses(
            json.dumps(
                {
                    'config': {
                        'item': [
                            {
                                'id': 1,
                                'dec': 'x',
                                'sp_tips': ['1_x'],
                                'sp_icon': ['1_../../bad'],
                            }
                        ]
                    }
                }
            ).encode()
        )


def test_glossary_icon_does_not_use_status_namespace():
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    c.execute("INSERT INTO glossary_entry VALUES (12,'寄生','A')")
    c.execute('INSERT INTO petglossaryentrylink VALUES (1,12)')
    replace_client_effect_tables(
        c, ClientEffectData((), ((12, 3),), [], [], '20261127104733')
    )
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT icon_kind,icon_asset_key,status_id FROM pet_special_effect'
    ).fetchone() == ('abnormal', '3', None)
    assert c.execute('SELECT icon_key FROM pet_special_effect').fetchone() == (None,)


def test_real_client_panel_and_conditional_display_references():
    fixture = json.loads(
        (
            Path(__file__).parent / 'fixtures/client-effect-panels-20261127.json'
        ).read_text(encoding='utf-8')
    )
    c = _connection()
    c.executemany('INSERT INTO pet VALUES (?,?)', fixture['pets'])
    c.executemany(
        'INSERT INTO glossary_entry VALUES (?,?,?)',
        [(r['id'], r['name'], r['desc']) for r in fixture['glossaries']],
    )
    c.executemany('INSERT INTO petglossaryentrylink VALUES (?,?)', fixture['links'])
    c.executemany(
        'INSERT INTO effect_description VALUES (?,?,?)', fixture['effect_descriptions']
    )
    c.executemany('INSERT INTO soulmark VALUES (?,?,?,?,?,?,?)', fixture['soulmarks'])
    c.executemany('INSERT INTO petsoulmarklink VALUES (?,?)', fixture['soulmark_links'])
    statuses = parse_special_effect_statuses(
        json.dumps({'config': {'item': fixture['statuses']}}).encode()
    )
    c.executemany(
        'INSERT INTO special_effect_status VALUES (?,?,?,?)',
        [(s.status_id, s.name, s.description, s.show_monster_id) for s in statuses],
    )
    data = ClientEffectData(
        tuple(PetEffectPanel(**p) for p in fixture['panels']),
        (),
        [],
        statuses,
        fixture['config_provenance']['version'],
        tuple(
            (r['id'], json.dumps(r, ensure_ascii=False)) for r in fixture['statuses']
        ),
    )
    replace_client_effect_tables(c, data)
    replace_pet_special_effect_facts(c, now=1)
    for pet_id, status_id in (
        (4035, 16),
        (4035, 17),
        (4677, 102),
        (4765, 119),
        (4797, 127),
        (4800, 137),
        (4364, 161),
        (4364, 162),
        (4554, 68),
        (4554, 69),
        (4765, 118),
    ):
        assert c.execute(
            'SELECT icon_kind,icon_key FROM pet_special_effect WHERE pet_id=? AND status_id=?',
            (pet_id, status_id),
        ).fetchone() == ('sign_buff', str(status_id))
    assert c.execute(
        'SELECT status_id FROM pet_special_effect WHERE pet_id=4554 AND glossary_id=234'
    ).fetchone() == (None,)
    assert not c.execute(
        "SELECT 1 FROM pet_special_effect WHERE pet_id=4554 AND name='圣告'"
    ).fetchone()
    assert c.execute(
        "SELECT reason FROM pet_special_effect_issue WHERE pet_id=4511 AND effect_name='不破诛罚'"
    ).fetchone() == ('unmatched_panel_heading',)
    before = c.execute(
        'SELECT pet_id,effect_key,status_id FROM pet_special_effect ORDER BY pet_id,effect_key'
    ).fetchall()
    replace_pet_special_effect_facts(c, now=2)
    assert (
        before
        == c.execute(
            'SELECT pet_id,effect_key,status_id FROM pet_special_effect ORDER BY pet_id,effect_key'
        ).fetchall()
    )


def test_display_conditions_are_not_unconditional_ownership():
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    raw = {'id': 10, 'dec': '状态', 'des': 'line1\\nline2', 'show_monster': ['2_1_0_1']}
    replace_client_effect_tables(
        c, ClientEffectData((), (), [], [], '20261127104733', ((10, json.dumps(raw)),))
    )
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT primary_rule,description FROM pet_special_effect'
    ).fetchone() == ('client_conditional_display', 'line1\nline2')
    source = c.execute(
        'SELECT source_kind,source_detail FROM pet_special_effect_source'
    ).fetchone()
    assert source[0] == 'client_status_display'
    assert json.loads(source[1])['show_monster'] == ['2_1_0_1']


@pytest.mark.parametrize(
    ('parser', 'prefix'),
    [
        (EffectDesParser, b'\x01\x01'),
        (SignIconFightParser, b'\x01\x01'),
        (PetEffectIconParser, b'\x01'),
    ],
)
def test_frozen_client_sources_reject_truncation_and_trailing_bytes(parser, prefix):
    valid = prefix + struct.pack('<i', 0)
    parser().parse(valid)
    with pytest.raises(ValueError, match='Unconsumed'):
        parser().parse(valid + b'garbage')
    with pytest.raises(IndexError, match='exceeds buffer'):
        parser().parse(valid[:-1])


@pytest.mark.parametrize('confirmed', [False, True])
def test_variant_name_is_scoped_to_verified_state_id_for_same_pet(confirmed):
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    c.execute("INSERT INTO glossary_entry VALUES (10,'分支','description')")
    c.execute('INSERT INTO petglossaryentrylink VALUES (1,10)')
    c.execute(
        "INSERT INTO special_effect_status_variant VALUES (151,2,'分支','','151_2')"
    )
    c.execute(
        "INSERT INTO special_effect_status_variant VALUES (999,2,'分支','','999_2')"
    )
    if confirmed:
        replace_client_effect_tables(
            c,
            ClientEffectData(
                (),
                (),
                [],
                [],
                '20261127104733',
                (
                    (
                        151,
                        json.dumps(
                            {'id': 151, 'dec': '状态', 'show_monster': ['2_1_0_1']}
                        ),
                    ),
                ),
            ),
        )
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT icon_kind,icon_asset_key FROM pet_special_effect WHERE glossary_id=10'
    ).fetchone() == (('sign_buff', '151_2') if confirmed else (None, None))


def test_variant_does_not_ignore_a_different_pet_at_its_display_threshold():
    c = _connection()
    c.execute("INSERT INTO pet VALUES (1,'test')")
    c.execute("INSERT INTO glossary_entry VALUES (10,'分支','description')")
    c.execute('INSERT INTO petglossaryentrylink VALUES (1,10)')
    c.execute(
        "INSERT INTO special_effect_status_variant VALUES (151,3,'分支','','151_3')"
    )
    raw = {'id': 151, 'dec': '状态', 'show_monster': ['2_1_0_1', '3_2_0_1']}
    replace_client_effect_tables(
        c, ClientEffectData((), (), [], [], '20261127104733', ((151, json.dumps(raw)),))
    )
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT icon_asset_key FROM pet_special_effect WHERE glossary_id=10'
    ).fetchone() == (None,)
