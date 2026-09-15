"""Pure domain values and semantic comparison rules for new-content releases."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any

AUTOCARD_SANCTUARY_EFFECT_CATEGORY = 'autocard_sanctuary_effect'
AUTOCARD_SANCTUARY_EFFECT_TABLE = 'autocard_season_effect'
PEAK_POOL_CATEGORY = 'peak_pool'
PEAK_EXPERT_POOL_CATEGORY = 'peak_expert_pool'
PEAK_MASTER_POOL_CATEGORY = 'peak_master_pool'
PEAK_POOL_FIELDS: dict[str, str] = {
    PEAK_POOL_CATEGORY: 'peak_pool_id',
    PEAK_EXPERT_POOL_CATEGORY: 'peak_expert_pool_id',
    PEAK_MASTER_POOL_CATEGORY: 'peak_cost_pool_id',
}
PEAK_POOL_SOURCE_TABLES: dict[str, str] = {
    PEAK_POOL_CATEGORY: 'peak_pool',
    PEAK_EXPERT_POOL_CATEGORY: 'peak_pool',
    PEAK_MASTER_POOL_CATEGORY: 'peak_cost_pool',
}
PEAK_POOL_CATEGORIES = frozenset(PEAK_POOL_FIELDS)
PEAK_POOL_MISSING_IS_UNLIMITED = frozenset({PEAK_MASTER_POOL_CATEGORY})
PET_VOLATILE_STATS = frozenset(
    {
        'peak_pool_id',
        'peak_expert_pool_id',
        'peak_cost_pool_id',
        'peak_pool_vote_id',
    }
)
PET_SKILL_RELATION_FIELDS = (
    'id',
    'learning_level',
    'is_special',
    'is_advanced',
    'is_fifth',
)
SEMANTIC_SCHEMA_VERSION = 6
SEMANTIC_MIGRATION_CATEGORIES_BY_VERSION: dict[int, frozenset[str]] = {
    2: frozenset({'pet', 'skill', 'equip', 'mount'}),
    3: frozenset({'mintmark'}),
    4: frozenset({'equip', 'mount'}),
}
SEMANTIC_MIGRATION_PRUNE_CATEGORIES_BY_VERSION: dict[int, frozenset[str]] = {
    2: frozenset({'pet', 'equip', 'mount'}),
    3: frozenset({'mintmark'}),
    4: frozenset({'equip', 'mount'}),
}
SEMANTIC_MIGRATION_SUPPRESS_MODIFIED_BY_VERSION: dict[int, frozenset[str]] = {
    4: frozenset({'equip', 'mount'}),
}
CONTENT_CATEGORIES = (
    'achievement',
    'pet',
    PEAK_POOL_CATEGORY,
    PEAK_EXPERT_POOL_CATEGORY,
    PEAK_MASTER_POOL_CATEGORY,
    'pet_skin',
    'skill',
    'mintmark',
    'suit',
    'equip',
    'mount',
    'autocard_card',
    'autocard_role',
    AUTOCARD_SANCTUARY_EFFECT_CATEGORY,
)
CATEGORY_SOURCE_TABLES: dict[str, tuple[str, ...]] = {
    'achievement': ('achievement',),
    'pet': ('pet',),
    **{
        category: ('pet', table)
        for category, table in PEAK_POOL_SOURCE_TABLES.items()
    },
    'pet_skin': ('pet_skin',),
    'skill': ('skill',),
    'mintmark': ('mintmark',),
    'suit': ('suit',),
    'equip': ('equip',),
    'mount': ('equip',),
    'autocard_card': ('autocard_card',),
    'autocard_role': ('autocard_role',),
    AUTOCARD_SANCTUARY_EFFECT_CATEGORY: (AUTOCARD_SANCTUARY_EFFECT_TABLE,),
}


@dataclass(frozen=True)
class ContentItem:
    category: str
    entity_id: int
    name: str
    sort_value: int
    payload: dict[str, Any]
    change_kind: str = 'added'

    @property
    def payload_json(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False, sort_keys=True)

    @property
    def semantic_payload(self) -> dict[str, Any]:
        """Return the payload fields that define the item's business meaning."""
        payload = dict(self.payload)
        if self.category == 'pet_skin':
            payload = {
                key: value for key, value in payload.items() if key != 'pet_name'
            }
        elif self.category == 'pet':
            if isinstance(stats := payload.get('stats'), dict):
                payload['stats'] = {
                    key: value
                    for key, value in stats.items()
                    if key not in PET_VOLATILE_STATS
                }
            if isinstance(skills := payload.get('skills'), list):
                payload['skills'] = [
                    {
                        field: skill[field]
                        for field in PET_SKILL_RELATION_FIELDS
                        if field in skill
                    }
                    for skill in skills
                    if isinstance(skill, dict)
                ]
        elif self.category == 'skill':
            payload.pop('pets', None)
        elif self.category == 'mintmark':
            payload.pop('rarity_id', None)
        return payload

    @property
    def semantic_key(self) -> str:
        """Return a stable fallback for an upstream item whose numeric ID changed."""
        return json.dumps(
            {
                'category': self.category,
                'name': self.name,
                'payload': self.semantic_payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @property
    def semantic_digest(self) -> str:
        return hashlib.sha256(self.semantic_key.encode('utf-8')).hexdigest()

    def with_change_kind(self, change_kind: str) -> ContentItem:
        return replace(self, change_kind=change_kind)


@dataclass(frozen=True)
class ReleaseState:
    config_version: str
    git_sha: str | None
    weekly_cycle: str
    baseline_established: bool
    items: tuple[ContentItem, ...]
    source_items: tuple[SourceSnapshotItem, ...] = field(default_factory=tuple)
    source_categories: frozenset[str] = field(default_factory=frozenset)
    category_states: tuple[CategoryState, ...] = field(default_factory=tuple)
    semantic_schema_version: int = SEMANTIC_SCHEMA_VERSION
    raw_items: tuple[ContentItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SourceSnapshotItem:
    category: str
    entity_id: int
    semantic_digest: str

    @classmethod
    def from_content(cls, item: ContentItem) -> SourceSnapshotItem:
        return cls(item.category, item.entity_id, item.semantic_digest)


@dataclass(frozen=True)
class CategoryState:
    category: str
    comparison_ready: bool
    reason: str


@dataclass(frozen=True)
class SourceHistoryAddition:
    """An entity added by the source repository between two published revisions."""

    category: str
    entity_id: int


def semantic_migration_categories(previous_version: int) -> frozenset[str]:
    return frozenset().union(
        *(
            categories
            for version, categories in SEMANTIC_MIGRATION_CATEGORIES_BY_VERSION.items()
            if previous_version < version <= SEMANTIC_SCHEMA_VERSION
        )
    )


def semantic_migration_prune_categories(previous_version: int) -> frozenset[str]:
    return frozenset().union(
        *(
            categories
            for version, categories in SEMANTIC_MIGRATION_PRUNE_CATEGORIES_BY_VERSION.items()
            if previous_version < version <= SEMANTIC_SCHEMA_VERSION
        )
    )


def semantic_migration_suppress_modified_categories(
    previous_version: int,
) -> frozenset[str]:
    return frozenset().union(
        *(
            categories
            for version, categories in (
                SEMANTIC_MIGRATION_SUPPRESS_MODIFIED_BY_VERSION.items()
            )
            if previous_version < version <= SEMANTIC_SCHEMA_VERSION
        )
    )
