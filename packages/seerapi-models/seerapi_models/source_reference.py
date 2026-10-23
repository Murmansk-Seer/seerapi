"""Lossless source evidence, not an assertion that a referenced pet exists."""

from hashlib import sha256
import json
import sqlite3

from sqlmodel import Field

from seerapi_models.build_model import BaseResModel, ConvertToORM


class UnresolvedPetReferenceBase(BaseResModel):
    owner_resource: str = Field(description='原始引用所属资源类型')
    owner_id: int = Field(description='原始引用所属条目ID')
    target_pet_id: int = Field(description='官方原始目标ID，不代表有效精灵外键')
    source_file: str = Field(description='Unity配置文件名')
    source_field: str = Field(description='原始引用字段')
    source_json: str = Field(description='完整原始条目JSON，保留空值和全部引用')
    source_sha256: str = Field(description='source_json的UTF-8 SHA256')
    reason: str = Field(default='target_missing', description='未能建立有效关联的原因')

    @classmethod
    def resource_name(cls) -> str:
        return 'unresolved_pet_reference'


class UnresolvedPetReference(
    UnresolvedPetReferenceBase, ConvertToORM['UnresolvedPetReferenceORM']
):
    @classmethod
    def get_orm_model(cls) -> type['UnresolvedPetReferenceORM']:
        return UnresolvedPetReferenceORM

    def to_orm(self) -> 'UnresolvedPetReferenceORM':
        return UnresolvedPetReferenceORM(**self.model_dump())


class UnresolvedPetReferenceORM(UnresolvedPetReferenceBase, table=True):
    """Raw IDs deliberately are not foreign keys; resolved relationship tables are."""


def validate_unresolved_pet_references(db: sqlite3.Connection) -> int:
    """Prove every retained source row has exactly its resolved + unresolved edges."""
    contracts = {
        'soulmark': ('effectIcon.json', 'pet_id', 'petsoulmarklink', 'soulmark_id'),
        'glossary_entry': (
            'effectDes.json',
            'monster',
            'petglossaryentrylink',
            'glossary_entry_id',
        ),
    }
    pets = {row[0] for row in db.execute('SELECT id FROM pet')}
    groups: dict[tuple[str, int], tuple[str, set[int]]] = {}
    records = db.execute(
        'SELECT owner_resource, owner_id, target_pet_id, source_file, source_field, '
        'source_json, source_sha256, reason FROM unresolved_pet_reference'
    ).fetchall()
    for resource, owner, target, filename, field, payload, digest, reason in records:
        if resource not in contracts:
            raise ValueError(f'Unsupported unresolved reference owner: {resource!r}')
        expected_file, expected_field, _, _ = contracts[resource]
        raw = json.loads(payload)
        if (filename, field, reason) != (
            expected_file,
            expected_field,
            'target_missing',
        ) or raw['id'] != owner:
            raise ValueError('Unresolved reference source identity mismatch')
        if sha256(payload.encode()).hexdigest() != digest:
            raise ValueError('Unresolved reference source SHA256 mismatch')
        if type(target) is not int or target <= 0 or target in pets:
            raise ValueError('Unresolved target must be an actually missing pet')
        if (
            db.execute(f'SELECT 1 FROM {resource} WHERE id=?', (owner,)).fetchone()
            is None
        ):
            raise ValueError('Unresolved reference owner is missing')
        previous, targets = groups.setdefault((resource, owner), (payload, set()))
        if previous != payload or target in targets:
            raise ValueError('Inconsistent or duplicate unresolved source reference')
        targets.add(target)
    for (resource, owner), (payload, missing) in groups.items():
        _, field, table, owner_column = contracts[resource]
        raw = json.loads(payload)[field]
        ids = raw if field == 'pet_id' else list(map(int, raw.split(',')))
        if any(type(value) is not int or value <= 0 for value in ids):
            raise ValueError('Invalid original pet reference')
        expected = set(ids)
        valid = {
            row[0]
            for row in db.execute(
                f'SELECT pet_id FROM {table} WHERE {owner_column}=?', (owner,)
            )
        }
        if valid != expected & pets or missing != expected - pets:
            raise ValueError(
                'Resolved + preserved references do not exactly match source'
            )
    return len(records)
