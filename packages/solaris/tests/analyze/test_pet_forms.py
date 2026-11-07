from copy import deepcopy
from typing import Any

import pytest

from solaris.analyze.analyzers.pet.pet import PetAnalyzer
from solaris.analyze.analyzers.pet.petbook import PetEncyclopediaAnalyzer


def fixture_source():
    common = {
        'type': 65,
        'gender': 0,
        'hp': 180,
        'atk': 160,
        'def': 120,
        'sp_atk': 80,
        'sp_def': 120,
        'spd': 140,
        'evolving_lv': 0,
    }
    rows: list[dict[str, Any]] = [
        dict(common, id=id_, def_name=name)
        for id_, name in [(13311, '圣光灵神SP'), (5270, '战斗副本'), (3311, '圣光灵神')]
    ]
    rows[0]['learnable_moves'] = {'move': [{'id': 38624, 'learning_lv': 66}]}
    rows[0]['extra_moves'] = {'move': [{'id': 38626, 'learning_lv': 71}]}
    return {
        'monsters.json': {'monsters': {'monster': rows}},
        'config.xml.PetXMLInfo.xml': {
            'Monsters': {
                'Monster': [
                    {'ID': id_, 'YieldingExp': 140, 'YieldingEV': 0, 'CatchRate': 0}
                    for id_ in (3311, 13311)
                ]
            }
        },
        'config.xml.PetBookXMLInfo.xml': {
            'root': {
                'Monster': [
                    {
                        'ID': id_,
                        'DefName': name,
                        'Features': '官方介绍',
                        'Height': '188',
                        'Weight': '78',
                    }
                    for id_, name in [(3311, '圣光灵神'), (13311, '圣光灵神SP')]
                ]
            }
        },
        'pet_gender.json': {0: {'id': 0, 'name': '无性别', 'description': ''}},
        'pet_vipbuff.json': {0: {'id': 0, 'name': '无', 'description': ''}},
        'pet_mount_type.json': {0: {'id': 0, 'name': '无', 'description': ''}},
    }


def analyzer(cls, data, monkeypatch):
    result = object.__new__(cls)
    monkeypatch.setattr(result, '_get_data', lambda _, name: data[name])
    monkeypatch.setattr(result, '_get_input_data', lambda *_: {})
    for name in (
        'pet_archive_story_book_data',
        'pet_advance_data',
        'pet_soulmark_data',
        'pet_left_and_right_data',
        'skill_activation_data',
    ):
        result.__dict__[name] = {}
    return result


def test_form_stats_skills_and_bidirectional_book_are_preserved(monkeypatch):
    data = fixture_source()
    before = deepcopy(data)
    pets = analyzer(PetAnalyzer, data, monkeypatch).analyze()[0].data
    books = analyzer(PetEncyclopediaAnalyzer, data, monkeypatch).analyze()[0].data
    assert set(pets) == set(books) == {3311, 13311}
    form = pets[13311]
    assert form.base_stats.total == 800
    assert form.base_stats.hp == 180
    assert form.type.id == 65
    assert [(s.skill.id, s.learning_level, s.is_fifth) for s in form.skill] == [
        (38624, 66, False),
        (38626, 71, True),
    ]
    assert form.encyclopedia_entry.id == books[13311].pet.id == 13311
    assert books[13311].introduction == '官方介绍'
    assert books[13311].height == 188
    assert form.to_orm().id == books[13311].to_orm().id == 13311
    assert data == before


def test_book_missing_monster_fails_before_generating_pets(monkeypatch):
    data = fixture_source()
    data['monsters.json']['monsters']['monster'] = [
        row
        for row in data['monsters.json']['monsters']['monster']
        if row['id'] != 13311
    ]
    with pytest.raises(ValueError, match='13311'):
        analyzer(PetAnalyzer, data, monkeypatch).analyze()
