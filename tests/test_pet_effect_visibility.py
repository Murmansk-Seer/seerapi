from __future__ import annotations

import json

import pytest
from test_pet_special_effect_facts import _connection

from scripts.client_effect_sources import ClientEffectData, replace_client_effect_tables
from seerapi_models.pet.special_effect import PetSpecialEffectORM
from solaris.analyze.output.pet_effect_panels import PetEffectPanel
from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)


def _fixture(mode='complete'):
    c = _connection()
    c.execute("INSERT INTO pet VALUES (9001,'arbitrary pet')")
    c.execute("INSERT INTO pet VALUES (9002,'other pet')")
    for gid, name in ((501, 'first form'), (502, 'second form')):
        if mode == 'missing' and gid == 502:
            continue
        c.execute('INSERT INTO glossary_entry VALUES (?,?,?)', (gid, name, 'effect'))
        c.execute('INSERT INTO petglossaryentrylink VALUES (?,?)', (9001, gid))
    raw = {
        'id': 321,
        'dec': 'container',
        'des': '',
        'show_monster': ['2_9001_0_1'],
    }
    if mode == 'description':
        raw['des'] = 'independent explanation'
    if mode == 'other_pet':
        raw['show_monster'].append('3_9002_0_1')
    if mode == 'no_applicable':
        raw['show_monster'] = ['4_9001_0_1']
    if mode == 'ambiguous':
        c.execute("INSERT INTO glossary_entry VALUES (503,'second form','different')")
        c.execute('INSERT INTO petglossaryentrylink VALUES (9001,503)')
    if mode == 'glossary':
        c.execute("INSERT INTO glossary_entry VALUES (504,'container','')")
        c.execute('INSERT INTO petglossaryentrylink VALUES (9001,504)')
    c.execute("INSERT INTO special_effect_status VALUES (321,'container','',0)")
    for value, name in ((2, 'first form'), (3, 'second form')):
        # Shared icon identity must not collapse distinct forms or decide visibility.
        c.execute(
            'INSERT INTO special_effect_status_variant VALUES (?,?,?,?,?)',
            (321, value, name, 'effect', '321'),
        )
    panels = (
        (
            PetEffectPanel(
                7, 9001, 8, '<indent=0><sprite=5><indent=15>container：', False, 'test'
            ),
        )
        if mode == 'panel'
        else ()
    )
    replace_client_effect_tables(
        c,
        ClientEffectData(
            panels,
            (),
            [],
            [],
            'test',
            ((321, json.dumps(raw)),),
        ),
    )
    return c


@pytest.mark.parametrize('mode', ['complete', 'other_pet'])
def test_complete_applicable_forms_hide_only_the_container(mode):
    c = _fixture(mode)
    for now in (1, 2):
        replace_pet_special_effect_facts(c, now=now)
        assert c.execute(
            'SELECT display_in_pet_info FROM pet_special_effect WHERE pet_id=9001 AND status_id=321'
        ).fetchone() == (0,)
        assert c.execute(
            'SELECT name,display_in_pet_info FROM pet_special_effect WHERE pet_id=9001 AND glossary_id IS NOT NULL ORDER BY glossary_id'
        ).fetchall() == [('first form', 1), ('second form', 1)]
        assert c.execute(
            "SELECT source_id FROM pet_special_effect_source WHERE pet_id=9001 AND source_kind='client_status_display'"
        ).fetchone() == (321,)
        if mode == 'other_pet':
            assert c.execute(
                'SELECT display_in_pet_info FROM pet_special_effect WHERE pet_id=9002 AND status_id=321'
            ).fetchone() == (1,)


@pytest.mark.parametrize(
    'mode',
    ['description', 'glossary', 'panel', 'missing', 'ambiguous', 'no_applicable'],
)
def test_independent_or_incomplete_states_remain_visible(mode):
    c = _fixture(mode)
    replace_pet_special_effect_facts(c, now=1)
    assert c.execute(
        'SELECT display_in_pet_info FROM pet_special_effect WHERE pet_id=9001 AND status_id=321'
    ).fetchone() == (1,)
    if mode in {'missing', 'ambiguous', 'no_applicable'}:
        assert c.execute(
            "SELECT 1 FROM pet_special_effect_issue WHERE pet_id=9001 AND reason='unresolved_status_container_display'"
        ).fetchone() == (1,)


def test_model_defaults_to_visible_and_roundtrips_false():
    data = {
        'pet_id': 1,
        'effect_key': 's:1',
        'name': 'state',
        'sort_kind': 'status',
        'primary_rule': 'test',
        'updated_at': 0,
    }
    assert PetSpecialEffectORM(**data).display_in_pet_info is True
    assert (
        PetSpecialEffectORM(**data, display_in_pet_info=False).model_dump()[
            'display_in_pet_info'
        ]
        is False
    )
