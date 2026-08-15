# SPDX-License-Identifier: MIT
"""Pure classic-skin image fallback and resolution rules."""

from __future__ import annotations

from dataclasses import dataclass

PET_IMAGE_ASSET_KINDS = ("head", "body")


@dataclass(frozen=True, slots=True)
class PetImageAssetCheck:
    kind: str
    resource_id: int
    url: str
    available: bool
    status: int
    content_type: str
    content_length: int | None
    error: str


@dataclass(frozen=True, slots=True)
class ClassicSkinImageSource:
    skin_id: int
    name: str
    resource_id: int


@dataclass(frozen=True, slots=True)
class PetImageSource:
    pet_id: int
    name: str
    resource_id: int


@dataclass(frozen=True, slots=True)
class SkinImageResolution:
    skin_id: int
    head_resource_id: int
    body_resource_id: int
    head_resolution: str
    body_resolution: str
    source_pet_id: int | None


def is_transient_asset_failure(check: PetImageAssetCheck) -> bool:
    return check.status == 0 or check.status == 429 or check.status >= 500


def is_confirmed_missing_asset(check: PetImageAssetCheck) -> bool:
    return not check.available and not is_transient_asset_failure(check)


def _candidates_by_name(
    pets: tuple[PetImageSource, ...],
) -> dict[str, list[PetImageSource]]:
    candidates: dict[str, list[PetImageSource]] = {}
    for pet in pets:
        candidates.setdefault(pet.name, []).append(pet)
    return candidates


def source_asset_keys_for_classic_skin_fallbacks(
    skins: tuple[ClassicSkinImageSource, ...],
    pets: tuple[PetImageSource, ...],
    direct_checks: dict[tuple[str, int], PetImageAssetCheck],
) -> set[tuple[str, int]]:
    candidates_by_name = _candidates_by_name(pets)
    asset_keys: set[tuple[str, int]] = set()
    for skin in skins:
        missing_kinds = tuple(
            kind
            for kind in PET_IMAGE_ASSET_KINDS
            if is_confirmed_missing_asset(direct_checks[(kind, skin.resource_id)])
        )
        candidates = candidates_by_name.get(skin.name, [])
        for candidate in candidates:
            asset_keys.update((kind, candidate.resource_id) for kind in missing_kinds)
            if len(candidates) > 1 and missing_kinds:
                asset_keys.update(
                    (kind, candidate.resource_id)
                    for kind in PET_IMAGE_ASSET_KINDS
                    if direct_checks[(kind, skin.resource_id)].available
                )
    return asset_keys


def content_hash_keys_for_classic_skin_fallbacks(
    skins: tuple[ClassicSkinImageSource, ...],
    pets: tuple[PetImageSource, ...],
    checks: dict[tuple[str, int], PetImageAssetCheck],
) -> set[tuple[str, int]]:
    candidates_by_name = _candidates_by_name(pets)
    asset_keys: set[tuple[str, int]] = set()
    for skin in skins:
        candidates = candidates_by_name.get(skin.name, [])
        if len(candidates) < 2:
            continue
        missing_kinds = tuple(
            kind
            for kind in PET_IMAGE_ASSET_KINDS
            if is_confirmed_missing_asset(checks[(kind, skin.resource_id)])
        )
        if not missing_kinds:
            continue
        counterpart_kinds = tuple(
            kind
            for kind in PET_IMAGE_ASSET_KINDS
            if checks[(kind, skin.resource_id)].available
        )
        for counterpart_kind in counterpart_kinds:
            asset_keys.add((counterpart_kind, skin.resource_id))
            asset_keys.update(
                (counterpart_kind, candidate.resource_id)
                for candidate in candidates
                if checks.get((counterpart_kind, candidate.resource_id))
                and checks[(counterpart_kind, candidate.resource_id)].available
            )
    return asset_keys


def resolve_classic_skin_image_resources(
    skins: tuple[ClassicSkinImageSource, ...],
    pets: tuple[PetImageSource, ...],
    checks: dict[tuple[str, int], PetImageAssetCheck],
    asset_hashes: dict[tuple[str, int], str],
) -> list[SkinImageResolution]:
    candidates_by_name = _candidates_by_name(pets)
    resolutions: list[SkinImageResolution] = []
    for skin in skins:
        direct_by_kind = {
            kind: checks[(kind, skin.resource_id)] for kind in PET_IMAGE_ASSET_KINDS
        }
        resource_ids = {
            kind: skin.resource_id if check.available else 0
            for kind, check in direct_by_kind.items()
        }
        resolution_names = {
            kind: (
                "direct_skin"
                if check.available
                else "unverified"
                if is_transient_asset_failure(check)
                else "unresolved"
            )
            for kind, check in direct_by_kind.items()
        }
        candidates = candidates_by_name.get(skin.name, [])
        resolved_source_ids: set[int] = set()

        for kind in PET_IMAGE_ASSET_KINDS:
            if resource_ids[kind] > 0 or resolution_names[kind] != "unresolved":
                continue
            source: PetImageSource | None = None
            resolution_name = "unresolved"
            if len(candidates) == 1:
                candidate = candidates[0]
                source_check = checks.get((kind, candidate.resource_id))
                if source_check is not None and source_check.available:
                    source = candidate
                    resolution_name = "unique_name_source"
            elif len(candidates) > 1:
                counterpart_kind = next(
                    (
                        other_kind
                        for other_kind in PET_IMAGE_ASSET_KINDS
                        if direct_by_kind[other_kind].available
                    ),
                    None,
                )
                expected_hash = (
                    asset_hashes.get((counterpart_kind, skin.resource_id))
                    if counterpart_kind is not None
                    else None
                )
                if expected_hash and counterpart_kind is not None:
                    matches = [
                        candidate
                        for candidate in candidates
                        if asset_hashes.get((counterpart_kind, candidate.resource_id))
                        == expected_hash
                        and checks.get((kind, candidate.resource_id)) is not None
                        and checks[(kind, candidate.resource_id)].available
                    ]
                    if len(matches) == 1:
                        source = matches[0]
                        resolution_name = "content_verified_source"
            if source is not None:
                resource_ids[kind] = source.resource_id
                resolution_names[kind] = resolution_name
                resolved_source_ids.add(source.pet_id)

        source_pet_id = (
            next(iter(resolved_source_ids)) if len(resolved_source_ids) == 1 else None
        )
        resolutions.append(
            SkinImageResolution(
                skin_id=skin.skin_id,
                head_resource_id=resource_ids["head"],
                body_resource_id=resource_ids["body"],
                head_resolution=resolution_names["head"],
                body_resolution=resolution_names["body"],
                source_pet_id=source_pet_id,
            )
        )
    return resolutions
