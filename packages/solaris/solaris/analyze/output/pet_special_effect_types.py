"""Internal value objects for deterministic pet special-effect facts."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

RULE_PRIORITY = {
    "direct_pet_glossary": 0,
    "direct_status_show_monster": 1,
    "glossary_link": 2,
    "skill_highlight_exact": 3,
    "soulmark_highlight_status": 4,
    "text_exact_name": 5,
    "effect_description_skill_name": 6,
    "unique_status_name": 7,
    "exact_status_description": 8,
    "status_description_similarity": 9,
    "same_description_lowest_status_id": 10,
}


def normalize_special_effect_text(value: str | None) -> str:
    """Normalize user-facing text for deterministic identity comparisons."""
    return re.sub(r"[\W_]+", "", value or "").casefold()


@dataclass(frozen=True, slots=True)
class StatusCandidate:
    """One official status definition that may provide an effect icon."""

    id: int
    name: str
    description: str
    show_monster_id: int


@dataclass(frozen=True, slots=True)
class EffectSource:
    """One upstream relation that justifies a resolved effect fact."""

    kind: str
    id: int
    rule: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EffectResolutionIssue:
    """An ambiguous association intentionally excluded from published facts."""

    pet_id: int
    effect_name: str
    candidate_kind: str
    candidate_id: int
    reason: str
    context: str | None


@dataclass(slots=True)
class SpecialEffectFact:
    """One deduplicated special-effect fact before it is written to SQLite."""

    pet_id: int
    effect_key: str
    name: str
    description: str | None
    glossary_id: int | None
    status_id: int | None
    primary_rule: str
    discovery_index: int
    sources: set[EffectSource] = field(default_factory=set)

    @property
    def sort_id(self) -> int | None:
        return self.glossary_id if self.glossary_id is not None else self.status_id

    @property
    def sort_kind(self) -> str:
        if self.glossary_id is not None:
            return "glossary"
        if self.status_id is not None:
            return "status"
        return "unresolved"


class SpecialEffectFactAccumulator:
    """Collect facts while enforcing per-pet glossary and status uniqueness."""

    def __init__(self) -> None:
        self._facts: list[SpecialEffectFact] = []
        self._by_glossary: dict[tuple[int, int], SpecialEffectFact] = {}
        self._by_status: dict[tuple[int, int], SpecialEffectFact] = {}
        self._by_text: dict[tuple[int, str, str], SpecialEffectFact] = {}

    @property
    def facts(self) -> list[SpecialEffectFact]:
        return self._facts

    def add(
        self,
        *,
        pet_id: int,
        name: str,
        description: str | None,
        source: EffectSource,
        glossary_id: int | None = None,
        status_id: int | None = None,
    ) -> SpecialEffectFact:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("special effect name must not be empty")
        text_key = (
            pet_id,
            normalize_special_effect_text(clean_name),
            normalize_special_effect_text(description),
        )
        candidates = [
            self._by_glossary.get((pet_id, glossary_id)) if glossary_id else None,
            self._by_status.get((pet_id, status_id)) if status_id else None,
            self._by_text.get(text_key),
        ]
        fact = next((candidate for candidate in candidates if candidate), None)
        if fact is None:
            fact = SpecialEffectFact(
                pet_id=pet_id,
                effect_key=text_key[1] or f"unnamed-{len(self._facts) + 1}",
                name=clean_name,
                description=description.strip() if description else None,
                glossary_id=None,
                status_id=None,
                primary_rule=source.rule,
                discovery_index=len(self._facts),
            )
            self._facts.append(fact)
            self._by_text[text_key] = fact
        fact = self._merge_identity(
            fact,
            glossary_id=glossary_id,
            status_id=status_id,
        )
        if fact.description is None and description:
            fact.description = description.strip()
        if RULE_PRIORITY[source.rule] < RULE_PRIORITY[fact.primary_rule]:
            fact.primary_rule = source.rule
        fact.sources.add(source)
        return fact

    def resolve_glossary(
        self,
        fact: SpecialEffectFact,
        glossary_id: int,
        source: EffectSource,
    ) -> SpecialEffectFact:
        target = self._by_glossary.get((fact.pet_id, glossary_id))
        if target is not None and target is not fact:
            self._merge(target, fact)
            fact = target
        fact = self._merge_identity(fact, glossary_id=glossary_id, status_id=None)
        if RULE_PRIORITY[source.rule] < RULE_PRIORITY[fact.primary_rule]:
            fact.primary_rule = source.rule
        fact.sources.add(source)
        return fact

    def _merge_identity(
        self,
        fact: SpecialEffectFact,
        *,
        glossary_id: int | None,
        status_id: int | None,
    ) -> SpecialEffectFact:
        if glossary_id is not None:
            other = self._by_glossary.get((fact.pet_id, glossary_id))
            if other is not None and other is not fact:
                self._merge(other, fact)
                fact = other
            fact.glossary_id = glossary_id
            fact.effect_key = f"g:{glossary_id}"
            self._by_glossary[(fact.pet_id, glossary_id)] = fact
        if status_id is not None:
            other = self._by_status.get((fact.pet_id, status_id))
            if other is not None and other is not fact:
                self._merge(fact, other)
            fact.status_id = status_id
            self._by_status[(fact.pet_id, status_id)] = fact
            if fact.glossary_id is None:
                fact.effect_key = f"s:{status_id}"
        return fact

    def _merge(
        self,
        target: SpecialEffectFact,
        duplicate: SpecialEffectFact,
    ) -> None:
        if target is duplicate:
            return
        if target.description is None:
            target.description = duplicate.description
        if duplicate.glossary_id is not None:
            target.glossary_id = duplicate.glossary_id
            target.effect_key = f"g:{duplicate.glossary_id}"
            self._by_glossary[(target.pet_id, duplicate.glossary_id)] = target
        if target.status_id is None and duplicate.status_id is not None:
            target.status_id = duplicate.status_id
            self._by_status[(target.pet_id, duplicate.status_id)] = target
        if RULE_PRIORITY[duplicate.primary_rule] < RULE_PRIORITY[target.primary_rule]:
            target.primary_rule = duplicate.primary_rule
        target.sources.update(duplicate.sources)
        for index, value in tuple(self._by_text.items()):
            if value is duplicate:
                self._by_text[index] = target
        for index, value in tuple(self._by_glossary.items()):
            if value is duplicate:
                self._by_glossary[index] = target
        for index, value in tuple(self._by_status.items()):
            if value is duplicate:
                self._by_status[index] = target
        self._facts.remove(duplicate)


__all__ = [
    "RULE_PRIORITY",
    "EffectResolutionIssue",
    "EffectSource",
    "SpecialEffectFact",
    "SpecialEffectFactAccumulator",
    "StatusCandidate",
    "normalize_special_effect_text",
]
