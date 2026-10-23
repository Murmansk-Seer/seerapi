"""Partition only documented pet associations, preserving missing targets losslessly."""

from collections.abc import Iterable
from hashlib import sha256
import json
from typing import Any

from seerapi_models.source_reference import UnresolvedPetReference


def official_pet_ids(data: dict[str, Any]) -> set[int]:
    return {row['id'] for row in data['monsters']['monster'] if row['id'] <= 9999}


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
            & ((1 << 63) - 1),
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
