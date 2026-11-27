"""Resolve official special-effect relations into deterministic fact candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from functools import cache
import re
import sqlite3

from .pet_effect_display_references import add_display_references
from .pet_effect_icon_identity import assign_icon_identities
from .pet_effect_panels import add_panel_references
from .pet_effect_visibility import assign_pet_info_visibility
from .pet_special_effect_types import (
    EffectDescriptionCandidate,
    EffectResolutionIssue,
    EffectSource,
    SpecialEffectFact,
    SpecialEffectFactAccumulator,
    StatusCandidate,
)

HIDDEN_SKILL_ID = 19002
RED_EFFECT_COLOR = '#f35555'
STATUS_HIGHLIGHT_COLORS = frozenset({'#f35555', '#57c975'})
GLOSSARY_ID_SUFFIX = re.compile(r'^(.*?)\((\d+)\)$')
COLOR_TOKEN = re.compile(
    r'\[color=(#[0-9a-fA-F]{6})\]|\[/color\]|\[sprite name=\w+\]|([^\[]+|\[)'
)
EFFECT_SEPARATORS = re.compile(r'[\s、，,；;/]+')


def _highlighted_terms(value: str | None, colors: Iterable[str]) -> list[str]:
    expected = {color.casefold() for color in colors}
    stack: list[str] = []
    terms: list[str] = []
    pieces: list[str] = []
    current_opens = 0
    last_batch = 0
    for match in COLOR_TOKEN.finditer(value or ''):
        color, plain = match.group(1), match.group(2)
        if color is not None:
            if not expected.intersection(stack) and color.casefold() in expected:
                pieces = []
            stack.append(color.casefold())
            current_opens += 1
        elif match.group(0) == '[/color]':
            active = bool(expected.intersection(stack))
            # Official Analyze text closes consecutively opened colors as a batch.
            for _ in range(min(max(1, last_batch), len(stack))):
                stack.pop()
            current_opens = last_batch = 0
            if active and not expected.intersection(stack):
                term = ''.join(pieces).strip()
                if term and term not in terms:
                    terms.append(term)
                pieces = []
        elif plain is not None and expected.intersection(stack):
            pieces.append(plain)
            last_batch, current_opens = current_opens, 0
        elif plain is not None:
            last_batch, current_opens = current_opens, 0
    return terms


def _marked_references(
    value: str, names: frozenset[str]
) -> list[tuple[str, int | None]]:
    """Require a whole label or an explicitly separated list, never substrings."""
    value = value.strip()
    if value in names:
        return [(value, None)]
    reference = GLOSSARY_ID_SUFFIX.fullmatch(value)
    if reference and reference[1] in names:
        return [(reference[1], int(reference[2]))]
    parts = EFFECT_SEPARATORS.split(value)
    if len(parts) < 2 or any(not part for part in parts):
        return []
    references = [_marked_references(part, names) for part in parts]
    if any(len(items) != 1 for items in references):
        return []
    return list(dict.fromkeys(items[0] for items in references))


def _load_glossaries(
    connection: sqlite3.Connection,
) -> tuple[dict[int, tuple[str, str]], dict[str, list[tuple[int, str]]]]:
    by_id: dict[int, tuple[str, str]] = {}
    by_name: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for glossary_id, name, description in connection.execute(
        'SELECT id, name, desc FROM glossary_entry ORDER BY id'
    ):
        clean_name = str(name or '').strip()
        if not clean_name:
            continue
        clean_description = str(description or '').strip()
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
        clean_name = str(name or '').strip()
        if clean_name:
            by_name[clean_name].append(
                StatusCandidate(
                    id=int(status_id),
                    name=clean_name,
                    description=str(description or '').strip(),
                    show_monster_id=int(show_monster_id or 0),
                )
            )
    return dict(by_name)


def _effect_descriptions(
    connection: sqlite3.Connection,
    glossaries: dict[int, tuple[str, str]],
) -> dict[str, list[EffectDescriptionCandidate]]:
    descriptions: dict[str, list[EffectDescriptionCandidate]] = defaultdict(list)
    for effect_id, name, description in connection.execute(
        'SELECT effect_id, name, description FROM effect_description ORDER BY effect_id'
    ):
        clean_name = str(name or '').strip()
        clean_description = str(description or '').strip()
        if not clean_name or not clean_description:
            continue
        glossary = glossaries.get(int(effect_id))
        glossary_id = (
            int(effect_id)
            if glossary is not None and glossary[0] == clean_name
            else None
        )
        descriptions[clean_name].append(
            EffectDescriptionCandidate(int(effect_id), glossary_id, clean_description)
        )
    return dict(descriptions)


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


def _choose_status(
    candidates: list[StatusCandidate],
    context: str,
) -> tuple[StatusCandidate | None, str | None]:
    unique = {candidate.id: candidate for candidate in candidates}
    if len(unique) == 1:
        return next(iter(unique.values())), 'unique_status_name'
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
            description=str(description or ''),
            glossary_id=int(glossary_id),
            source=EffectSource(
                'pet_glossary',
                int(glossary_id),
                'direct_pet_glossary',
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
                    'status',
                    status.id,
                    'direct_status_show_monster',
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
        context = '\n'.join(
            value.strip()
            for value in (
                str(desc or ''),
                str(analyze_desc or ''),
                str(adjustment or ''),
            )
            if value and value.strip()
        )
        if context:
            yield int(pet_id), int(soulmark_id), context


def _select_text_candidates(
    candidates: list[EffectDescriptionCandidate],
    established: list[SpecialEffectFact],
    context: str,
    *,
    marked: bool = False,
) -> list[EffectDescriptionCandidate]:
    if established:
        return [
            candidate
            for candidate in candidates
            if any(
                (
                    candidate.glossary_id is not None
                    and candidate.glossary_id == fact.glossary_id
                )
                for fact in established
            )
        ]
    if not marked:
        return []
    if len(candidates) == 1:
        return candidates
    return []


def _skill_description_references(
    skill_name: str,
    descriptions: dict[str, list[EffectDescriptionCandidate]],
) -> tuple[tuple[str, EffectDescriptionCandidate], ...]:
    if not skill_name:
        return ()
    pattern = re.compile(
        rf'(?:[\"“「『《【]{re.escape(skill_name)}[\"”」』》】]|技能[：:\s]*{re.escape(skill_name)}(?=[，。；、\s]|$))'
    )
    return tuple(
        (name, candidate)
        for name, candidates in descriptions.items()
        for candidate in candidates
        if skill_name in candidate.description and pattern.search(candidate.description)
    )


def _add_text_effects(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    statuses_by_name: dict[str, list[StatusCandidate]],
    effect_descriptions: dict[str, list[EffectDescriptionCandidate]],
    issues: list[EffectResolutionIssue],
) -> None:
    official_names = frozenset(effect_descriptions)
    if not official_names:
        return

    @cache
    def skill_references(
        name: str,
    ) -> tuple[tuple[str, EffectDescriptionCandidate], ...]:
        # Shared skills recur across pets and text fields; retain only this build's evidence.
        return _skill_description_references(name, effect_descriptions)

    established: dict[tuple[int, str], list[SpecialEffectFact]] = defaultdict(list)
    for fact in facts.facts:
        established[fact.pet_id, fact.name].append(fact)

    def candidates_for(
        pet_id: int,
        name: str,
        context: str,
        *,
        marked: bool = False,
        reference_id: int | None = None,
    ) -> list[EffectDescriptionCandidate]:
        candidates = effect_descriptions[name]
        if reference_id is not None:
            candidates = [item for item in candidates if item.id == reference_id]
            if not candidates:
                _append_issue(
                    issues,
                    pet_id=pet_id,
                    effect_name=name,
                    candidate_kind='effect_description',
                    candidates=(reference_id,),
                    reason='invalid_marked_effect_reference',
                    context=context,
                )
                return []
            return candidates
        existing = established.get((pet_id, name), [])
        selected = _select_text_candidates(
            candidates,
            existing,
            context,
            marked=marked,
        )
        if not selected:
            _append_issue(
                issues,
                pet_id=pet_id,
                effect_name=name,
                candidate_kind='effect_description',
                candidates=(candidate.id for candidate in candidates),
                reason=(
                    'ambiguous_text_effect_name'
                    if marked or existing
                    else 'unverified_text_ownership'
                ),
                context=context,
            )
        return selected

    def add_marked(pet_id: int, source: EffectSource, context: str) -> set[str]:
        names = official_names | frozenset(statuses_by_name)
        colors = (
            (RED_EFFECT_COLOR,) if source.kind == 'skill' else STATUS_HIGHLIGHT_COLORS
        )
        matched: set[str] = set()
        for label in _highlighted_terms(context, colors):
            for name, reference_id in _marked_references(label, names):
                matched.add(name)
                if name in effect_descriptions:
                    for candidate in candidates_for(
                        pet_id,
                        name,
                        context,
                        marked=True,
                        reference_id=reference_id,
                    ):
                        facts.add(
                            pet_id=pet_id,
                            name=name,
                            description=candidate.description,
                            glossary_id=candidate.glossary_id,
                            source=source,
                        )
                elif reference_id is None:
                    candidates = statuses_by_name.get(name, [])
                    status, _rule = _choose_status(candidates, context)
                    if status is not None:
                        facts.add(
                            pet_id=pet_id,
                            name=name,
                            description=status.description,
                            status_id=status.id,
                            source=source,
                        )
                    else:
                        _append_issue(
                            issues,
                            pet_id=pet_id,
                            effect_name=name,
                            candidate_kind='status',
                            candidates=(item.id for item in candidates),
                            reason='ambiguous_marked_status',
                            context=context,
                        )
                else:
                    _append_issue(
                        issues,
                        pet_id=pet_id,
                        effect_name=name,
                        candidate_kind='effect_description',
                        candidates=(reference_id,),
                        reason='invalid_marked_effect_reference',
                        context=context,
                    )
        return matched

    name_pattern = re.compile(
        '|'.join(
            re.escape(name) for name in sorted(official_names, key=len, reverse=True)
        )
    )
    for pet_id, skill_id, skill_name, text in _skill_texts(connection):
        highlighted_names = add_marked(
            pet_id,
            EffectSource('skill', skill_id, 'skill_highlight_exact', skill_name),
            text,
        )
        for name in sorted(set(name_pattern.findall(text)) - highlighted_names):
            if not established.get((pet_id, name)):
                candidates_for(pet_id, name, text)
        for name, candidate in skill_references(skill_name):
            if not established.get((pet_id, name)):
                candidates_for(pet_id, name, candidate.description)
    for pet_id, soulmark_id, context in _soulmark_texts(connection):
        marked_names = add_marked(
            pet_id,
            EffectSource('soulmark', soulmark_id, 'soulmark_highlight_exact'),
            context,
        )
        for name in sorted(set(name_pattern.findall(context)) - marked_names):
            if not established.get((pet_id, name)):
                candidates_for(pet_id, name, context)


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
    placeholders = ', '.join('?' for _ in parent_ids)
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
                    'glossary_link',
                    int(parent_id),
                    'glossary_link',
                ),
            )


def collect_pet_special_effect_facts(
    connection: sqlite3.Connection,
    *,
    available_icon_keys: frozenset[str] | None = None,
) -> tuple[SpecialEffectFactAccumulator, list[EffectResolutionIssue]]:
    """Collect all official effect relations before publishing fact tables."""
    glossaries, _glossary_by_name = _load_glossaries(connection)
    statuses_by_name = _load_statuses(connection)
    descriptions = _effect_descriptions(connection, glossaries)
    facts = SpecialEffectFactAccumulator()
    issues: list[EffectResolutionIssue] = []

    _add_direct_sources(connection, facts, statuses_by_name)
    _add_text_effects(connection, facts, statuses_by_name, descriptions, issues)
    _add_linked_glossaries(connection, facts, glossaries)
    add_display_references(connection, facts, issues)
    add_panel_references(connection, facts, statuses_by_name, issues)
    assign_icon_identities(connection, facts, issues)
    assign_pet_info_visibility(connection, facts, issues)
    return facts, issues


__all__ = ['collect_pet_special_effect_facts']
