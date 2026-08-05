"""Resolve official special-effect relations into deterministic fact candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from difflib import SequenceMatcher
import re
import sqlite3

from .pet_special_effect_types import (
    EffectResolutionIssue,
    EffectSource,
    SpecialEffectFactAccumulator,
    StatusCandidate,
    normalize_special_effect_text,
)

HIDDEN_SKILL_ID = 19002
RED_EFFECT_COLOR = "#f35555"
STATUS_HIGHLIGHT_COLORS = frozenset({"#f35555", "#57c975"})
GLOSSARY_ID_SUFFIX = re.compile(r"\(\d+\)$")
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")
COLOR_TOKEN = re.compile(
    r"\[color=(#[0-9a-fA-F]{6})\]|\[/color\]|\[sprite name=\w+\]|([^\[]+|\[)"
)
EFFECT_SEPARATORS = re.compile(r"[\s、，,；;]+")


def _description_score(candidate: str | None, context: str | None) -> float:
    normalized_candidate = normalize_special_effect_text(candidate)
    normalized_context = normalize_special_effect_text(context)
    if not normalized_candidate or not normalized_context:
        return 0.0
    if normalized_candidate in normalized_context:
        return 2.0
    candidate_numbers = set(NUMBER_PATTERN.findall(candidate or ""))
    context_numbers = set(NUMBER_PATTERN.findall(context or ""))
    numeric_score = (
        len(candidate_numbers & context_numbers) / len(candidate_numbers)
        if candidate_numbers
        else 0.0
    )
    return (
        SequenceMatcher(None, normalized_candidate, normalized_context).ratio()
        + numeric_score * 0.5
    )


def _highlighted_terms(value: str | None, colors: Iterable[str]) -> list[str]:
    expected = {color.casefold() for color in colors}
    stack: list[str] = []
    terms: list[str] = []
    for match in COLOR_TOKEN.finditer(value or ""):
        color, plain = match.group(1), match.group(2)
        if color is not None:
            stack.append(color.casefold())
        elif match.group(0) == "[/color]":
            if stack:
                stack.pop()
        elif plain is not None and expected.intersection(stack):
            term = GLOSSARY_ID_SUFFIX.sub("", plain.strip())
            if term and term not in terms:
                terms.append(term)
    return terms


def _split_official_names(value: str, names: frozenset[str]) -> list[str]:
    compact = EFFECT_SEPARATORS.sub("", value.strip())
    if not compact:
        return []
    ordered_names = tuple(
        sorted((name for name in names if name in compact), key=len, reverse=True)
    )
    matches: list[list[str] | None] = [None] * (len(compact) + 1)
    matches[0] = []
    for start, prefix in enumerate(matches[:-1]):
        if prefix is None:
            continue
        for name in ordered_names:
            if compact.startswith(name, start):
                end = start + len(name)
                if matches[end] is None:
                    matches[end] = [*prefix, name]
    return list(dict.fromkeys(matches[-1] or []))


def _load_glossaries(
    connection: sqlite3.Connection,
) -> tuple[dict[int, tuple[str, str]], dict[str, list[tuple[int, str]]]]:
    by_id: dict[int, tuple[str, str]] = {}
    by_name: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for glossary_id, name, description in connection.execute(
        "SELECT id, name, desc FROM glossary_entry ORDER BY id"
    ):
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        clean_description = str(description or "").strip()
        by_id[int(glossary_id)] = (clean_name, clean_description)
        by_name[clean_name].append((int(glossary_id), clean_description))
    return by_id, dict(by_name)


def _load_statuses(
    connection: sqlite3.Connection,
) -> dict[str, list[StatusCandidate]]:
    by_name: dict[str, list[StatusCandidate]] = defaultdict(list)
    for status_id, name, description, show_monster_id in connection.execute(
        """
        SELECT status_id, name, description, show_monster_id
        FROM special_effect_status
        ORDER BY status_id, name
        """
    ):
        clean_name = str(name or "").strip()
        if clean_name:
            by_name[clean_name].append(
                StatusCandidate(
                    id=int(status_id),
                    name=clean_name,
                    description=str(description or "").strip(),
                    show_monster_id=int(show_monster_id or 0),
                )
            )
    return dict(by_name)


def _effect_descriptions(
    connection: sqlite3.Connection,
    glossaries: dict[int, tuple[str, str]],
) -> dict[str, tuple[int | None, str]]:
    descriptions: dict[str, tuple[int | None, str]] = {}
    for effect_id, name, description in connection.execute(
        "SELECT effect_id, name, description FROM effect_description ORDER BY effect_id"
    ):
        clean_name = str(name or "").strip()
        clean_description = str(description or "").strip()
        if not clean_name or not clean_description:
            continue
        glossary = glossaries.get(int(effect_id))
        glossary_id = (
            int(effect_id)
            if glossary is not None and glossary[0] == clean_name
            else None
        )
        descriptions.setdefault(clean_name, (glossary_id, clean_description))
    return descriptions


def _append_issue(
    issues: list[EffectResolutionIssue],
    *,
    pet_id: int,
    effect_name: str,
    candidate_kind: str,
    candidates: Iterable[int],
    reason: str,
    context: str | None,
) -> None:
    issues.extend(
        EffectResolutionIssue(
            pet_id=pet_id,
            effect_name=effect_name,
            candidate_kind=candidate_kind,
            candidate_id=candidate_id,
            reason=reason,
            context=context,
        )
        for candidate_id in sorted(set(candidates))
    )


def _resolve_glossary_candidates(
    facts: SpecialEffectFactAccumulator,
    by_name: dict[str, list[tuple[int, str]]],
    issues: list[EffectResolutionIssue],
) -> None:
    for fact in tuple(facts.facts):
        if fact.glossary_id is not None:
            continue
        candidates = by_name.get(fact.name, [])
        if len(candidates) == 1:
            facts.resolve_glossary(
                fact,
                candidates[0][0],
                EffectSource(
                    "glossary",
                    candidates[0][0],
                    "exact_status_description",
                ),
            )
            continue
        exact = [
            glossary_id
            for glossary_id, description in candidates
            if normalize_special_effect_text(description)
            and normalize_special_effect_text(description)
            == normalize_special_effect_text(fact.description)
        ]
        if len(exact) == 1:
            facts.resolve_glossary(
                fact,
                exact[0],
                EffectSource("glossary", exact[0], "exact_status_description"),
            )
        elif candidates:
            _append_issue(
                issues,
                pet_id=fact.pet_id,
                effect_name=fact.name,
                candidate_kind="glossary",
                candidates=(candidate[0] for candidate in candidates),
                reason="ambiguous_glossary_name",
                context=fact.description,
            )


def _choose_status(
    candidates: list[StatusCandidate],
    context: str,
) -> tuple[StatusCandidate | None, str | None]:
    if len(candidates) == 1:
        return candidates[0], "unique_status_name"
    normalized = {
        normalize_special_effect_text(candidate.description)
        for candidate in candidates
    }
    if len(normalized) == 1 and "" not in normalized:
        return min(candidates, key=lambda candidate: candidate.id), (
            "same_description_lowest_status_id"
        )
    ranked = sorted(
        ((_description_score(item.description, context), item) for item in candidates),
        key=lambda row: (row[0], -row[1].id),
        reverse=True,
    )
    best_score, best = ranked[0]
    next_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score >= 0.25 and best_score > next_score + 0.03:
        return best, "status_description_similarity"
    return None, None


def _add_direct_sources(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    statuses_by_name: dict[str, list[StatusCandidate]],
) -> None:
    for pet_id, glossary_id, name, description in connection.execute(
        """
        SELECT link.pet_id, glossary.id, glossary.name, glossary.desc
        FROM petglossaryentrylink AS link
        JOIN glossary_entry AS glossary ON glossary.id = link.glossary_entry_id
        ORDER BY link.pet_id, glossary.id
        """
    ):
        facts.add(
            pet_id=int(pet_id),
            name=str(name),
            description=str(description or ""),
            glossary_id=int(glossary_id),
            source=EffectSource(
                "pet_glossary",
                int(glossary_id),
                "direct_pet_glossary",
            ),
        )
    for candidates in statuses_by_name.values():
        for status in candidates:
            if status.show_monster_id <= 0:
                continue
            facts.add(
                pet_id=status.show_monster_id,
                name=status.name,
                description=status.description,
                status_id=status.id,
                source=EffectSource(
                    "status",
                    status.id,
                    "direct_status_show_monster",
                ),
            )


def _skill_texts(connection: sqlite3.Connection) -> Iterable[tuple[int, int, str, str]]:
    query = """
        SELECT link.pet_id, skill.id, skill.name, value
        FROM skillinpetorm AS link
        JOIN skill ON skill.id = link.skill_id
        JOIN (
            SELECT id AS skill_id, info AS value FROM skill
            UNION ALL
            SELECT skill_id, analyze_info FROM skilleffectlink
            JOIN skill_effect_in_use
                ON skill_effect_in_use.id = skilleffectlink.effect_in_use_id
            UNION ALL
            SELECT skill_id, info FROM skilleffectlink
            JOIN skill_effect_in_use
                ON skill_effect_in_use.id = skilleffectlink.effect_in_use_id
            UNION ALL
            SELECT skill_id, analyze_info FROM skillfriendskilleffectlink
            JOIN skill_effect_in_use
                ON skill_effect_in_use.id = skillfriendskilleffectlink.effect_in_use_id
            UNION ALL
            SELECT skill_id, info FROM skillfriendskilleffectlink
            JOIN skill_effect_in_use
                ON skill_effect_in_use.id = skillfriendskilleffectlink.effect_in_use_id
            UNION ALL
            SELECT skill.id, skill_hide_effect.description
            FROM skill
            JOIN skill_hide_effect ON skill_hide_effect.id = skill.hide_effect_id
        ) AS texts ON texts.skill_id = skill.id
        WHERE skill.id <> ? AND value IS NOT NULL AND value <> ''
        ORDER BY link.pet_id, skill.id
    """
    for pet_id, skill_id, skill_name, value in connection.execute(
        query,
        (HIDDEN_SKILL_ID,),
    ):
        yield int(pet_id), int(skill_id), str(skill_name), str(value)


def _soulmark_texts(
    connection: sqlite3.Connection,
) -> Iterable[tuple[int, int, str]]:
    for pet_id, soulmark_id, desc, analyze_desc, adjustment in connection.execute(
        """
        SELECT link.pet_id, soulmark.id, soulmark.desc, soulmark.analyze_desc,
               soulmark.desc_formatting_adjustment
        FROM petsoulmarklink AS link
        JOIN soulmark ON soulmark.id = link.soulmark_id
        ORDER BY link.pet_id, soulmark.id
        """
    ):
        context = "\n".join(
            value.strip()
            for value in (
                str(desc or ""),
                str(analyze_desc or ""),
                str(adjustment or ""),
            )
            if value and value.strip()
        )
        if context:
            yield int(pet_id), int(soulmark_id), context


def _add_text_effects(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    statuses_by_name: dict[str, list[StatusCandidate]],
    effect_descriptions: dict[str, tuple[int | None, str]],
    issues: list[EffectResolutionIssue],
) -> None:
    official_names = frozenset(effect_descriptions)
    if not official_names:
        return
    name_pattern = re.compile(
        "|".join(
            re.escape(name) for name in sorted(official_names, key=len, reverse=True)
        )
    )
    for pet_id, skill_id, skill_name, text in _skill_texts(connection):
        matched = set(name_pattern.findall(text))
        highlighted_names = {
            name
            for highlighted in _highlighted_terms(text, (RED_EFFECT_COLOR,))
            for name in _split_official_names(highlighted, official_names)
        }
        matched.update(highlighted_names)
        for name in sorted(matched):
            glossary_id, description = effect_descriptions[name]
            facts.add(
                pet_id=pet_id,
                name=name,
                description=description,
                glossary_id=glossary_id,
                source=EffectSource(
                    "skill",
                    skill_id,
                    "skill_highlight_exact"
                    if name in highlighted_names
                    else "text_exact_name",
                    skill_name,
                ),
            )
        for name, (glossary_id, description) in effect_descriptions.items():
            if skill_name and skill_name in description:
                facts.add(
                    pet_id=pet_id,
                    name=name,
                    description=description,
                    glossary_id=glossary_id,
                    source=EffectSource(
                        "skill",
                        skill_id,
                        "effect_description_skill_name",
                        skill_name,
                    ),
                )
    for pet_id, soulmark_id, context in _soulmark_texts(connection):
        for name in sorted(set(name_pattern.findall(context))):
            glossary_id, description = effect_descriptions[name]
            facts.add(
                pet_id=pet_id,
                name=name,
                description=description,
                glossary_id=glossary_id,
                source=EffectSource(
                    "soulmark",
                    soulmark_id,
                    "text_exact_name",
                ),
            )
        for name in _highlighted_terms(context, STATUS_HIGHLIGHT_COLORS):
            candidates = statuses_by_name.get(name, [])
            status, rule = (
                _choose_status(candidates, context) if candidates else (None, None)
            )
            if status is None:
                if candidates:
                    _append_issue(
                        issues,
                        pet_id=pet_id,
                        effect_name=name,
                        candidate_kind="status",
                        candidates=(candidate.id for candidate in candidates),
                        reason="ambiguous_soulmark_highlight_status",
                        context=context,
                    )
                continue
            facts.add(
                pet_id=pet_id,
                name=status.name,
                description=status.description,
                status_id=status.id,
                source=EffectSource(
                    "soulmark",
                    soulmark_id,
                    rule or "soulmark_highlight_status",
                ),
            )


def _attach_named_statuses(
    facts: SpecialEffectFactAccumulator,
    statuses_by_name: dict[str, list[StatusCandidate]],
    issues: list[EffectResolutionIssue],
) -> None:
    for fact in tuple(facts.facts):
        if fact.status_id is not None:
            continue
        candidates = statuses_by_name.get(fact.name, [])
        if not candidates:
            continue
        status, rule = _choose_status(candidates, fact.description or "")
        if status is None:
            _append_issue(
                issues,
                pet_id=fact.pet_id,
                effect_name=fact.name,
                candidate_kind="status",
                candidates=(candidate.id for candidate in candidates),
                reason="ambiguous_named_status",
                context=fact.description,
            )
            continue
        facts.add(
            pet_id=fact.pet_id,
            name=fact.name,
            description=fact.description or status.description,
            glossary_id=fact.glossary_id,
            status_id=status.id,
            source=EffectSource(
                "status",
                status.id,
                rule or "unique_status_name",
            ),
        )


def _add_linked_glossaries(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    glossaries: dict[int, tuple[str, str]],
) -> None:
    parent_pairs = [
        (fact.pet_id, fact.glossary_id)
        for fact in facts.facts
        if fact.glossary_id is not None
    ]
    if not parent_pairs:
        return
    parent_ids = sorted({glossary_id for _pet_id, glossary_id in parent_pairs})
    placeholders = ", ".join("?" for _ in parent_ids)
    links = connection.execute(
        f"""
        SELECT source_id, target_id
        FROM glossaryentrylink
        WHERE source_id IN ({placeholders}) AND source_id <> target_id
        ORDER BY source_id, target_id
        """,
        parent_ids,
    )
    pet_ids_by_parent: dict[int, set[int]] = defaultdict(set)
    for pet_id, parent_id in parent_pairs:
        pet_ids_by_parent[parent_id].add(pet_id)
    for parent_id, target_id in links:
        target = glossaries.get(int(target_id))
        if target is None:
            continue
        for pet_id in pet_ids_by_parent[int(parent_id)]:
            facts.add(
                pet_id=pet_id,
                name=target[0],
                description=target[1],
                glossary_id=int(target_id),
                source=EffectSource(
                    "glossary_link",
                    int(parent_id),
                    "glossary_link",
                ),
            )


def collect_pet_special_effect_facts(
    connection: sqlite3.Connection,
) -> tuple[SpecialEffectFactAccumulator, list[EffectResolutionIssue]]:
    """Collect all official effect relations before publishing fact tables."""
    glossaries, glossary_by_name = _load_glossaries(connection)
    statuses_by_name = _load_statuses(connection)
    descriptions = _effect_descriptions(connection, glossaries)
    facts = SpecialEffectFactAccumulator()
    issues: list[EffectResolutionIssue] = []

    _add_direct_sources(connection, facts, statuses_by_name)
    _add_text_effects(connection, facts, statuses_by_name, descriptions, issues)
    _resolve_glossary_candidates(facts, glossary_by_name, issues)
    _attach_named_statuses(facts, statuses_by_name, issues)
    _resolve_glossary_candidates(facts, glossary_by_name, issues)
    _add_linked_glossaries(connection, facts, glossaries)
    _attach_named_statuses(facts, statuses_by_name, issues)
    _resolve_glossary_candidates(facts, glossary_by_name, issues)
    return facts, issues


__all__ = ["collect_pet_special_effect_facts"]
