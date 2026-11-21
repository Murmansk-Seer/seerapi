# SPDX-License-Identifier: MIT
"""Official display-form resources and explicitly declared pet families."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

if __package__:
    from .config_package_sources import BytesReader
else:
    from config_package_sources import BytesReader


@dataclass(frozen=True, slots=True)
class PetFormResource:
    pet_id: int
    skin_id: int
    form_index: int
    resource_id: int


@dataclass(frozen=True, slots=True)
class PetFormMember:
    canonical_pet_id: int
    pet_id: int


def parse_pet_form_resources(data: bytes) -> list[PetFormResource]:
    reader = BytesReader(data)
    rows: list[PetFormResource] = []
    if reader.read_bool():
        for _ in range(_count(reader)):
            reader.read_i32()  # Config row ID, not a display ID.
            pet_id = reader.read_i32()
            replacements = reader.read_text()
            skin_id = reader.read_i32()
            if (pet_id > 0) == (skin_id > 0) or min(pet_id, skin_id) < 0:
                raise ValueError('invalid pet_skin_poly owner')
            for index, value in enumerate(replacements.split(';'), start=1):
                # Preserve positions: the client keeps invalid entries as zero.
                resource_id = int(value) if value.strip().isdigit() else 0
                if resource_id > 0:
                    rows.append(PetFormResource(pet_id, skin_id, index, resource_id))
    reader.require_finished()
    return rows


def parse_pet_form_members(data: bytes) -> list[PetFormMember]:
    reader = BytesReader(data)
    members: set[PetFormMember] = set()
    if reader.read_bool():
        for _ in range(_count(reader)):
            reader.read_text()  # activation flags
            pets = (
                [reader.read_i32() for _ in range(_count(reader))]
                if reader.read_bool()
                else []
            )
            reader.read_text()  # change flags
            reader.read_text()  # description
            canonical = reader.read_i32()
            reader.read_i32()  # user-info key
            if canonical <= 0 or any(pet <= 0 for pet in pets):
                raise ValueError('invalid petCompositio member')
            members.update(PetFormMember(canonical, pet) for pet in (*pets, canonical))
    reader.require_finished()
    return sorted(members, key=lambda row: (row.canonical_pet_id, row.pet_id))


def _count(reader: BytesReader) -> int:
    count = reader.read_i32()
    if not 0 <= count <= 100000:
        raise ValueError('invalid pet form record count')
    return count


def replace_pet_form_tables(
    conn: sqlite3.Connection,
    resources: list[PetFormResource],
    members: list[PetFormMember],
) -> None:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS pet_form_resource ('
        'pet_id INTEGER NOT NULL, skin_id INTEGER NOT NULL, '
        'form_index INTEGER NOT NULL CHECK(form_index > 0), '
        'resource_id INTEGER NOT NULL CHECK(resource_id > 0), '
        'PRIMARY KEY(pet_id, skin_id, form_index))'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS pet_form_member ('
        'canonical_pet_id INTEGER NOT NULL, pet_id INTEGER NOT NULL, '
        'PRIMARY KEY(canonical_pet_id, pet_id))'
    )
    conn.execute('DELETE FROM pet_form_resource')
    conn.execute('DELETE FROM pet_form_member')
    conn.executemany(
        'INSERT INTO pet_form_resource VALUES (?, ?, ?, ?)',
        [
            (row.pet_id, row.skin_id, row.form_index, row.resource_id)
            for row in resources
        ],
    )
    conn.executemany(
        'INSERT INTO pet_form_member VALUES (?, ?)',
        [(row.canonical_pet_id, row.pet_id) for row in members],
    )
