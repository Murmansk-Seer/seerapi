# SPDX-License-Identifier: MIT
"""SQLite writer for official Autocard release tables."""

from __future__ import annotations

import sqlite3

if __package__:
    from .autocard_sources import AutocardData
    from .config_package_sources import AutocardSeasonEffect
    from .json_value_helpers import (
        compact_json as _dump_json,
    )
    from .json_value_helpers import (
        item_int as _item_int,
    )
    from .json_value_helpers import (
        item_text as _item_text,
    )
else:
    from autocard_sources import AutocardData  # type: ignore[import-not-found]
    from config_package_sources import (  # type: ignore[import-not-found]
        AutocardSeasonEffect,
    )
    from json_value_helpers import (  # type: ignore[import-not-found]
        compact_json as _dump_json,
    )
    from json_value_helpers import (
        item_int as _item_int,
    )
    from json_value_helpers import (
        item_text as _item_text,
    )

AUTOCARD_CARD_TABLE = "autocard_card"
AUTOCARD_ROLE_TABLE = "autocard_role"
AUTOCARD_ROLE_RAW_TABLE = "autocard_role_raw"
AUTOCARD_NATURE_TABLE = "autocard_nature"
AUTOCARD_BUFF_TABLE = "autocard_buff"
AUTOCARD_SEASON_EFFECT_TABLE = "autocard_season_effect"

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def replace_autocard_role_table(
    conn: sqlite3.Connection,
    data: AutocardData,
    updated_at: float,
) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS autocard_element_type (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_ROLE_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            health INTEGER NOT NULL,
            skill_desc TEXT NOT NULL,
            is_passive_skill BOOLEAN NOT NULL,
            skill_cost INTEGER,
            skill_game_limit INTEGER,
            skill_round_limit INTEGER,
            element_type_id INTEGER NOT NULL,
            FOREIGN KEY (element_type_id) REFERENCES autocard_element_type(id)
        )
        """
    )
    columns = _table_columns(conn, AUTOCARD_ROLE_TABLE)
    official_columns = {
        "id",
        "name",
        "description",
        "health",
        "skill_desc",
        "is_passive_skill",
        "skill_cost",
        "skill_game_limit",
        "skill_round_limit",
        "element_type_id",
    }
    if columns != official_columns:
        raise RuntimeError(
            "Unsupported autocard_role schema; expected official columns, got: "
            + ", ".join(sorted(columns))
        )

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_ROLE_RAW_TABLE} (
            role_id INTEGER PRIMARY KEY,
            pic_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            skill_upgrade TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (role_id) REFERENCES {AUTOCARD_ROLE_TABLE}(id)
        )
        """
    )
    raw_columns = _table_columns(conn, AUTOCARD_ROLE_RAW_TABLE)
    expected_raw_columns = {
        "role_id",
        "pic_id",
        "skill_id",
        "skill_name",
        "skill_upgrade",
        "raw_json",
        "source",
        "updated_at",
    }
    if raw_columns != expected_raw_columns:
        raise RuntimeError(
            "Unsupported autocard_role_raw schema; expected sidecar columns, got: "
            + ", ".join(sorted(raw_columns))
        )

    element_type_rows = [
        (_item_int(item, "id"), _item_text(item, "name"))
        for item in data.natures
        if _item_int(item, "id") > 0
    ]
    role_items = [
        item
        for item in data.roles
        if 0 < _item_int(item, "id") < 10000
    ]
    official_role_rows: list[tuple[object, ...]] = []
    raw_role_rows: list[tuple[object, ...]] = []
    for item in role_items:
        id_ = _item_int(item, "id")
        nature = _item_int(item, "nature")
        element_type_id = nature or 999
        is_passive_skill = not bool(
            _item_int(item, "skillType", "skill_type")
        )
        skill_cost = None
        skill_game_limit = None
        skill_round_limit = None
        if not is_passive_skill:
            skill_cost = _item_int(item, "skillCostNum", "skill_cost_num")
            skill_game_limit = _item_int(
                item, "skillGameLimit", "skill_game_limit"
            )
            skill_round_limit = _item_int(
                item, "skillRoundLimit", "skill_round_limit"
            )
        official_role_rows.append(
            (
                id_,
                _item_text(item, "name"),
                _item_text(item, "desc"),
                _item_int(item, "health"),
                _item_text(item, "skillTxt", "skill_txt"),
                int(is_passive_skill),
                skill_cost,
                skill_game_limit,
                skill_round_limit,
                element_type_id,
            )
        )
        raw_role_rows.append(
            (
                id_,
                _item_int(item, "picID", "pic_id"),
                _item_int(item, "skillID", "skill_id"),
                _item_text(item, "skillName", "skill_name"),
                _item_text(item, "skillUpgrade", "skill_upgrade"),
                _dump_json(item),
                data.source,
                updated_at,
            )
        )

    conn.execute(f"DELETE FROM {AUTOCARD_ROLE_RAW_TABLE}")
    conn.execute(f"DELETE FROM {AUTOCARD_ROLE_TABLE}")
    if element_type_rows:
        placeholders = ", ".join("?" for _ in element_type_rows)
        conn.execute(
            f"DELETE FROM autocard_element_type WHERE id NOT IN ({placeholders})",
            tuple(id_ for id_, _ in element_type_rows),
        )
    conn.executemany(
        """
        INSERT INTO autocard_element_type (id, name)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET name = excluded.name
        """,
        element_type_rows,
    )
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_ROLE_TABLE} (
            id,
            name,
            description,
            health,
            skill_desc,
            is_passive_skill,
            skill_cost,
            skill_game_limit,
            skill_round_limit,
            element_type_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        official_role_rows,
    )
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_ROLE_RAW_TABLE} (
            role_id,
            pic_id,
            skill_id,
            skill_name,
            skill_upgrade,
            raw_json,
            source,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        raw_role_rows,
    )

    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{AUTOCARD_ROLE_TABLE}_name
        ON {AUTOCARD_ROLE_TABLE} (name)
        """
    )


def replace_autocard_tables(
    conn: sqlite3.Connection,
    data: AutocardData,
    updated_at: float,
) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_CARD_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type INTEGER NOT NULL,
            nature INTEGER NOT NULL,
            attack INTEGER NOT NULL,
            health INTEGER NOT NULL,
            level INTEGER NOT NULL,
            cost INTEGER NOT NULL,
            compose INTEGER NOT NULL,
            card_text TEXT NOT NULL,
            description TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_CARD_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_CARD_TABLE}
            (
                id,
                name,
                type,
                nature,
                attack,
                health,
                level,
                cost,
                compose,
                card_text,
                description,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "name"),
                _item_int(item, "type"),
                _item_int(item, "nature"),
                _item_int(item, "attack"),
                _item_int(item, "health"),
                _item_int(item, "level"),
                _item_int(item, "cost"),
                _item_int(item, "compose"),
                _item_text(item, "cardTxt", "card_txt"),
                _item_text(item, "des"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.cards
            if _item_int(item, "id") > 0
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{AUTOCARD_CARD_TABLE}_name
        ON {AUTOCARD_CARD_TABLE} (name)
        """
    )

    replace_autocard_role_table(conn, data, updated_at)

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_NATURE_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_NATURE_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_NATURE_TABLE}
            (id, name, raw_json, source, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "name"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.natures
            if _item_int(item, "id") > 0
        ],
    )

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_BUFF_TABLE} (
            id INTEGER PRIMARY KEY,
            object TEXT NOT NULL,
            param TEXT NOT NULL,
            param_description TEXT NOT NULL,
            is_death_effect INTEGER NOT NULL,
            is_place_effect INTEGER NOT NULL,
            effect_icon TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_BUFF_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_BUFF_TABLE}
            (
                id,
                object,
                param,
                param_description,
                is_death_effect,
                is_place_effect,
                effect_icon,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "object"),
                _item_text(item, "param"),
                _item_text(item, "paramDes", "param_des"),
                _item_int(item, "IsDeathEffect", "is_death_effect"),
                _item_int(item, "IsPlaceEffect", "is_place_effect"),
                _item_text(item, "effectIcon", "effect_icon"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.buffs
            if _item_int(item, "id") > 0
        ],
    )


def replace_autocard_season_effect_table(
    conn: sqlite3.Connection,
    effects: list[AutocardSeasonEffect],
    updated_at: float,
) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_SEASON_EFFECT_TABLE} (
            id INTEGER PRIMARY KEY,
            sanctuary_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            buff_id TEXT NOT NULL,
            buff_param TEXT NOT NULL,
            count_buff_id TEXT NOT NULL,
            count_type INTEGER NOT NULL,
            count_num INTEGER NOT NULL,
            unlock_round INTEGER NOT NULL,
            pic_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            stage INTEGER NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_SEASON_EFFECT_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_SEASON_EFFECT_TABLE}
            (
                id,
                sanctuary_id,
                name,
                description,
                buff_id,
                buff_param,
                count_buff_id,
                count_type,
                count_num,
                unlock_round,
                pic_id,
                season_id,
                stage,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.effect_id,
                item.sanctuary_id,
                item.name,
                item.description,
                item.buff_id,
                item.buff_param,
                item.count_buff_id,
                item.count_type,
                item.count_num,
                item.unlock_round,
                item.pic_id,
                item.season_id,
                item.stage,
                _dump_json(
                    {
                        "id": item.effect_id,
                        "sanctuary_id": item.sanctuary_id,
                        "name": item.name,
                        "description": item.description,
                        "buff_id": item.buff_id,
                        "buff_param": item.buff_param,
                        "count_buff_id": item.count_buff_id,
                        "count_type": item.count_type,
                        "count_num": item.count_num,
                        "unlock_round": item.unlock_round,
                        "pic_id": item.pic_id,
                        "season_id": item.season_id,
                        "stage": item.stage,
                    }
                ),
                "ConfigPackage/autocardSeasonEffect.bytes",
                updated_at,
            )
            for item in effects
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
            idx_{AUTOCARD_SEASON_EFFECT_TABLE}_sanctuary
        ON {AUTOCARD_SEASON_EFFECT_TABLE}
            (sanctuary_id, unlock_round, id)
        """
    )


