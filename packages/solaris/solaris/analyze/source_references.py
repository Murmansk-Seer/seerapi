"""Partition only documented pet associations, preserving missing targets losslessly."""

from collections.abc import Iterable
from hashlib import sha256
import json
from typing import Any

from seerapi_models.source_reference import UnresolvedPetReference


def official_pet_ids(data: dict[str, Any], encyclopedia_ids: Iterable[int]) -> set[int]:
    """Include official encyclopedia forms, not arbitrary high-ID battle copies."""
    available = {row['id'] for row in data['monsters']['monster']}
    encyclopedia = set(encyclopedia_ids)
    missing = encyclopedia - available
    if missing:
        raise ValueError(
            f'Official encyclopedia entries missing monster records: {sorted(missing)}'
        )
    # Battle copies also have low IDs beyond the ordinary encyclopedia range.
    # Keep legacy ordinary monsters without their own book entry inside that
    # range, and admit higher forms only with explicit official book evidence.
    ordinary_limit = max((id_ for id_ in encyclopedia if id_ <= 9999), default=0)
    return {id_ for id_ in available if id_ <= ordinary_limit} | encyclopedia


def partition_pet_ids(
    ids: Iterable[int], known: set[int]
) -> tuple[list[int], list[int]]:
    valid, missing = [], []
    for pet_id in ids:
        if type(pet_id) is not int or pet_id <= 0:
            raise ValueError(f'Invalid official pet reference: {pet_id!r}')
        (valid if pet_id in known else missing).append(pet_id)
    return valid, missing


def preserve_missing_pet_refs(
    resource: str, filename: str, field: str, row: dict[str, Any], missing: list[int]
) -> list[UnresolvedPetReference]:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = sha256(payload.encode()).hexdigest()
    return [
        UnresolvedPetReference(
            id=int.from_bytes(
                sha256(f'{resource}:{row["id"]}:{field}:{pet_id}'.encode()).digest()[
                    :8
                ],
                'big',
            )
            & ((1 << 53) - 1),
            owner_resource=resource,
            owner_id=row['id'],
            target_pet_id=pet_id,
            source_file=filename,
            source_field=field,
            source_json=payload,
            source_sha256=digest,
        )
        for pet_id in dict.fromkeys(missing)
    ]
