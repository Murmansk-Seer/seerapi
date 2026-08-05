"""Published, build-time-resolved pet special-effect facts.

These tables are derived when the SeerAPI SQLite release is built. Runtime
consumers read the resulting facts and provenance instead of re-running text
matching against raw skill, soulmark, glossary, and status tables.
"""

from sqlmodel import Field, SQLModel


class PetSpecialEffectORM(SQLModel, table=True):
    """One resolved special effect shown for one pet."""

    __tablename__ = "pet_special_effect"  # type: ignore[reportAssignmentType]

    pet_id: int = Field(primary_key=True, foreign_key="pet.id")
    effect_key: str = Field(primary_key=True)
    glossary_id: int | None = Field(default=None, foreign_key="glossary_entry.id")
    status_id: int | None = Field(default=None)
    name: str
    description: str | None = Field(default=None)
    sort_id: int | None = Field(default=None)
    sort_kind: str
    primary_rule: str
    updated_at: float


class PetSpecialEffectSourceORM(SQLModel, table=True):
    """A source record and resolution rule supporting a special-effect fact."""

    __tablename__ = "pet_special_effect_source"  # type: ignore[reportAssignmentType]

    pet_id: int = Field(primary_key=True, foreign_key="pet.id")
    effect_key: str = Field(primary_key=True)
    source_kind: str = Field(primary_key=True)
    source_id: int = Field(primary_key=True)
    resolution_rule: str = Field(primary_key=True)
    source_detail: str | None = Field(default=None)
    updated_at: float


class PetSpecialEffectIssueORM(SQLModel, table=True):
    """A candidate deliberately not resolved into a special-effect fact."""

    __tablename__ = "pet_special_effect_issue"  # type: ignore[reportAssignmentType]

    pet_id: int = Field(primary_key=True, foreign_key="pet.id")
    effect_name: str = Field(primary_key=True)
    candidate_kind: str = Field(primary_key=True)
    candidate_id: int = Field(primary_key=True)
    reason: str = Field(primary_key=True)
    context: str | None = Field(default=None)
    updated_at: float


class PetSoulmarkDisplayORM(SQLModel, table=True):
    """Stable display order for a pet's base, intensified, and advance soulmarks."""

    __tablename__ = "pet_soulmark_display"  # type: ignore[reportAssignmentType]

    pet_id: int = Field(primary_key=True, foreign_key="pet.id")
    soulmark_id: int = Field(primary_key=True, foreign_key="soulmark.id")
    root_soulmark_id: int = Field(foreign_key="soulmark.id")
    display_order: int
    display_kind: str
    updated_at: float


class PetSoulmarkDisplayAdditionORM(SQLModel, table=True):
    """A declared display-only soulmark fact missing from raw package data."""

    __tablename__ = "pet_soulmark_display_addition"  # type: ignore[reportAssignmentType]

    pet_id: int = Field(primary_key=True, foreign_key="pet.id")
    display_id: int = Field(primary_key=True)
    description: str
    analyze_description: str | None = Field(default=None)
    formatting_adjustment: str | None = Field(default=None)
    intensified: bool
    intensified_to_id: int | None = Field(default=None)
    is_adv: bool
    pve_effective: bool | None = Field(default=None)
    tags_json: str
    display_order: int
    source: str
    updated_at: float


__all__ = [
    "PetSoulmarkDisplayAdditionORM",
    "PetSoulmarkDisplayORM",
    "PetSpecialEffectIssueORM",
    "PetSpecialEffectORM",
    "PetSpecialEffectSourceORM",
]
