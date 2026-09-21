# SPDX-License-Identifier: MIT
"""Pure parser for official ConfigPackage partner-contract data."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True, slots=True)
class PetPartnerGroup:
    group_id: int
    name: str
    member_pet_ids: tuple[int, ...]
    cost_item_id: int
    cost_item_name: str
    cost_item_quantity: int


@dataclass(frozen=True, slots=True)
class PetPartnerUpgrade:
    pet_id: int
    before_description: str
    after_description: str
    skill_id: int | None


@dataclass(frozen=True, slots=True)
class PetPartnerData:
    groups: list[PetPartnerGroup]
    upgrades: list[PetPartnerUpgrade]


def parse_pet_partner_data(
    data: bytes,
    *,
    schema_version: int,
    group_type: str,
    cost_item_id: int,
    cost_item_name: str,
    descriptions_reversed: bool,
) -> PetPartnerData:
    """Validate and normalize the published partner-contract source."""

    raw = json.loads(data.decode('utf-8-sig'))
    if not isinstance(raw, dict):
        raise ValueError('Partner contracts root must be an object')
    if raw.get('schema_version') != schema_version:
        raise ValueError(
            f'Unsupported partner contracts schema: {raw.get("schema_version")!r}'
        )
    source = raw.get('source')
    if (
        not isinstance(source, dict)
        or source.get('package') != 'ConfigPackage'
        or not isinstance(source.get('config_package_version'), str)
        or not source['config_package_version'].strip()
    ):
        raise ValueError('Partner contracts are not sourced from ConfigPackage')

    group_rows = raw.get('groups')
    if not isinstance(group_rows, list):
        raise ValueError('Partner contracts groups must be a list')

    groups: list[PetPartnerGroup] = []
    member_pet_ids: set[int] = set()
    seen_group_ids: set[int] = set()
    for index, row in enumerate(group_rows):
        if not isinstance(row, dict):
            raise ValueError(f'Partner contract group {index} must be an object')
        group_id = _contract_int(row.get('key'), f'groups[{index}].key')
        row_group_type = _text(row, 'type').strip()
        name = _text(row, 'name').strip()
        cost = _contract_int(row.get('cost'), f'groups[{index}].cost')
        raw_members = row.get('member_pet_ids')
        if not isinstance(raw_members, list):
            raise ValueError(f'Partner contract group {group_id} has invalid members')
        members = tuple(
            _contract_int(member_id, f'groups[{index}].member_pet_ids[{member_index}]')
            for member_index, member_id in enumerate(raw_members)
        )
        if (
            group_id <= 0
            or not row_group_type
            or not name
            or cost <= 0
            or len(members) < 2
            or group_id in seen_group_ids
            or any(member_id <= 0 for member_id in members)
            or len(set(members)) != len(members)
            or any(member_id in member_pet_ids for member_id in members)
        ):
            raise ValueError(f'Invalid partner contract group {group_id}')
        if row_group_type != group_type:
            continue
        seen_group_ids.add(group_id)
        member_pet_ids.update(members)
        groups.append(
            PetPartnerGroup(
                group_id=group_id,
                name=name,
                member_pet_ids=members,
                cost_item_id=cost_item_id,
                cost_item_name=cost_item_name,
                cost_item_quantity=cost,
            )
        )

    upgrade_rows = raw.get('upgrades')
    if not isinstance(upgrade_rows, list):
        raise ValueError('Partner contract upgrades must be a list')

    upgrades: dict[int, PetPartnerUpgrade] = {}
    for index, row in enumerate(upgrade_rows):
        if not isinstance(row, dict):
            raise ValueError(f'Partner contract upgrade {index} must be an object')
        pet_id = _contract_int(row.get('pet_id'), f'upgrades[{index}].pet_id')
        if pet_id <= 0 or pet_id not in member_pet_ids or pet_id in upgrades:
            continue
        raw_skill_ids = row.get('skill_ids', [])
        if not isinstance(raw_skill_ids, list):
            raise ValueError(f'Partner contract upgrade {pet_id} has invalid skill IDs')
        skill_id = next(
            (
                value
                for skill_index, raw_skill_id in enumerate(raw_skill_ids)
                if (
                    value := _contract_int(
                        raw_skill_id,
                        f'upgrades[{index}].skill_ids[{skill_index}]',
                    )
                )
                > 0
            ),
            None,
        )
        before_description = _text(row, 'before_description').strip()
        after_description = _text(row, 'after_description').strip()
        if descriptions_reversed:
            before_description, after_description = (
                after_description,
                before_description,
            )
        upgrades[pet_id] = PetPartnerUpgrade(
            pet_id=pet_id,
            before_description=before_description,
            after_description=after_description,
            skill_id=skill_id,
        )

    return PetPartnerData(
        groups=sorted(groups, key=lambda group: group.group_id),
        upgrades=[upgrades[pet_id] for pet_id in sorted(upgrades)],
    )


def _contract_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(
        value, (str, bytes, bytearray, int, float)
    ):
        raise ValueError(f'Invalid contract {label}: {value!r}')
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'Invalid contract {label}: {value!r}') from error


def _text(item: dict[object, object], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ''
