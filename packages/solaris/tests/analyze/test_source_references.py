from copy import deepcopy
from hashlib import sha256
import json
import sqlite3

import pytest

from seerapi_models.source_reference import validate_unresolved_pet_references
from solaris.analyze.analyzers.glossary import GlossaryAnalyzer
from solaris.analyze.analyzers.unresolved_pet_reference import (
    UnresolvedPetReferenceAnalyzer,
)
from solaris.analyze.source_references import partition_pet_ids


def source():
    return {
        'monsters.json': {'monsters': {'monster': [{'id': 4542}]}},
        'effectIcon.json': {
            'root': {'effect': [{'id': 1753, 'pet_id': [4543], 'tips': '', 'args': ''}]}
        },
        'effectDes.json': {
            'root': {
                'item': [
                    {
                        'id': 117,
                        'kinddes': '吸取体力',
                        'desc': '',
                        'kind': 1,
                        'link': '',
                        'monster': '4543,4542',
                    }
                ]
            }
        },
    }


def analyze(cls, data, monkeypatch):
    analyzer = object.__new__(cls)
    monkeypatch.setattr(analyzer, '_get_data', lambda _, name: data[name])
    return analyzer.analyze()[0].data


def test_raw_evidence_and_resolved_json_partition_without_mutation(monkeypatch):
    data = source()
    original = deepcopy(data)
    records = analyze(UnresolvedPetReferenceAnalyzer, data, monkeypatch)
    assert len(records) == 2
    assert records == analyze(UnresolvedPetReferenceAnalyzer, data, monkeypatch)
    for row in records.values():
        assert row.target_pet_id == 4543
        assert row.source_sha256 == sha256(row.source_json.encode()).hexdigest()
        assert (
            json.loads(row.source_json)
            in data[row.source_file]['root'][
                'effect' if row.source_file == 'effectIcon.json' else 'item'
            ]
        )
    glossary = analyze(GlossaryAnalyzer, data, monkeypatch)
    assert [ref.id for ref in glossary[117].pet] == [4542]
    assert data == original
    # When the official pet really appears, no raw tombstone remains.
    data['monsters.json']['monsters']['monster'].append({'id': 4543})
    assert analyze(UnresolvedPetReferenceAnalyzer, data, monkeypatch) == {}
    assert [
        ref.id for ref in analyze(GlossaryAnalyzer, data, monkeypatch)[117].pet
    ] == [4543, 4542]


@pytest.mark.parametrize('invalid', [True, 0, -1, '4543', None])
def test_invalid_reference_is_not_quarantined(invalid):
    with pytest.raises(ValueError, match='Invalid official'):
        partition_pet_ids([invalid], {4542})


def fixture_db(records):
    db = sqlite3.connect(':memory:')
    db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE pet(id INTEGER PRIMARY KEY);
        INSERT INTO pet VALUES(4542);
        CREATE TABLE soulmark(id INTEGER PRIMARY KEY);
        INSERT INTO soulmark VALUES(1753);
        CREATE TABLE glossary_entry(id INTEGER PRIMARY KEY);
        INSERT INTO glossary_entry VALUES(117);
        CREATE TABLE petsoulmarklink(pet_id INTEGER REFERENCES pet(id), soulmark_id INTEGER REFERENCES soulmark(id));
        CREATE TABLE petglossaryentrylink(pet_id INTEGER REFERENCES pet(id), glossary_entry_id INTEGER REFERENCES glossary_entry(id));
        INSERT INTO petglossaryentrylink VALUES(4542,117);
        CREATE TABLE unresolved_pet_reference(id INTEGER PRIMARY KEY, owner_resource TEXT, owner_id INTEGER, target_pet_id INTEGER, source_file TEXT, source_field TEXT, source_json TEXT, source_sha256 TEXT, reason TEXT);
    """)
    for row in records.values():
        values = row.model_dump()
        db.execute(
            'INSERT INTO unresolved_pet_reference ('
            + ','.join(values)
            + ') VALUES ('
            + ','.join('?' for _ in values)
            + ')',
            tuple(values.values()),
        )
    return db


def test_preserved_reference_validation_and_foreign_keys_remain_strict(monkeypatch):
    records = analyze(UnresolvedPetReferenceAnalyzer, source(), monkeypatch)
    db = fixture_db(records)
    try:
        assert validate_unresolved_pet_references(db) == 2
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('SELECT 1 FROM pet WHERE id=4543').fetchone() is None
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO petsoulmarklink VALUES(4543,1753)')
        db.execute("UPDATE unresolved_pet_reference SET source_sha256='broken'")
        with pytest.raises(ValueError, match='SHA256'):
            validate_unresolved_pet_references(db)
    finally:
        db.close()


@pytest.mark.parametrize(
    'corruption',
    [
        'DELETE FROM petglossaryentrylink',
        "UPDATE unresolved_pet_reference SET target_pet_id=4544 WHERE owner_resource='soulmark'",
        "UPDATE unresolved_pet_reference SET source_file='other.json'",
        "UPDATE unresolved_pet_reference SET owner_resource='pet'",
    ],
)
def test_corrupt_or_incomplete_preservation_blocks_release(monkeypatch, corruption):
    db = fixture_db(analyze(UnresolvedPetReferenceAnalyzer, source(), monkeypatch))
    try:
        db.execute(corruption)
        with pytest.raises(ValueError, match=r'reference|source'):
            validate_unresolved_pet_references(db)
    finally:
        db.close()
