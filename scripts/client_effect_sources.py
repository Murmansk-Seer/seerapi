"""Freeze client panel, glossary icon and conditional status configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3

from solaris.analyze.output.pet_effect_panels import PetEffectPanel, replace_panel_table
from solaris.parse.parsers.effect_des import EffectDesParser
from solaris.parse.parsers.pet_effect_icon import PetEffectIconParser
from solaris.parse.parsers.sign_icon_fight import SignIconFightParser

if __package__:
    from .effect_metadata_sources import (
        EffectDescription,
        SpecialEffectStatus,
        parse_effect_descriptions,
        parse_special_effect_statuses,
    )
else:
    from effect_metadata_sources import (
        EffectDescription,
        SpecialEffectStatus,
        parse_effect_descriptions,
        parse_special_effect_statuses,
    )

CLIENT_EFFECT_ASSETS = {
    'petEffectIcon.bytes',
    'effectDes.bytes',
    'signIcon_fight.bytes',
}


@dataclass(frozen=True, slots=True)
class ClientEffectData:
    panels: tuple[PetEffectPanel, ...]
    glossary_icons: tuple[tuple[int, int], ...]
    descriptions: list[EffectDescription]
    statuses: list[SpecialEffectStatus]
    config_version: str
    status_configs: tuple[tuple[int, str], ...] = ()


def parse_client_effect_data(
    assets: dict[str, bytes], version: str
) -> ClientEffectData:
    panels = PetEffectIconParser().parse(assets['petEffectIcon.bytes'])['data']
    glossary = EffectDesParser().parse(assets['effectDes.bytes'])
    statuses = SignIconFightParser().parse(assets['signIcon_fight.bytes'])
    for rows, key in (
        (panels, 'id'),
        (glossary['root']['item'], 'id'),
        (statuses['config']['item'], 'id'),
    ):
        ids = [row[key] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate client effect configuration ID')
    return ClientEffectData(
        tuple(
            PetEffectPanel(
                r['id'],
                r['petid'],
                r['effecticonid'],
                r['Desc'],
                bool(r['isAdv']),
                version,
            )
            for r in panels
        ),
        tuple((r['id'], r['icon']) for r in glossary['root']['item']),
        parse_effect_descriptions(json.dumps(glossary, ensure_ascii=False).encode()),
        parse_special_effect_statuses(
            json.dumps(statuses, ensure_ascii=False).encode()
        ),
        version,
        tuple(
            (row['id'], json.dumps(row, ensure_ascii=False, sort_keys=True))
            for row in statuses['config']['item']
        ),
    )


def replace_client_effect_tables(
    connection: sqlite3.Connection, data: ClientEffectData
) -> None:
    replace_panel_table(connection, data.panels)
    connection.execute('DROP TABLE IF EXISTS special_effect_glossary_icon')
    connection.execute(
        'CREATE TABLE special_effect_glossary_icon (glossary_id INTEGER PRIMARY KEY, icon_id INTEGER NOT NULL, config_version TEXT NOT NULL)'
    )
    connection.executemany(
        'INSERT INTO special_effect_glossary_icon VALUES (?,?,?)',
        [(gid, icon, data.config_version) for gid, icon in data.glossary_icons],
    )
    connection.execute('DROP TABLE IF EXISTS special_effect_status_display_rule')
    connection.execute(
        'CREATE TABLE special_effect_status_display_rule (status_id INTEGER NOT NULL, rule_index INTEGER NOT NULL, raw_rule TEXT NOT NULL, state_value INTEGER, pet_id INTEGER, show_icon INTEGER, show_frame INTEGER, config_version TEXT NOT NULL, PRIMARY KEY(status_id,rule_index))'
    )
    rows = {}
    for status in data.statuses:
        for index, raw in enumerate(status.display_rules):
            parts = raw.split('_')
            parsed = (
                tuple(int(value) for value in parts)
                if len(parts) == 4 and all(v.lstrip('-').isdecimal() for v in parts)
                else (None,) * 4
            )
            rows[status.status_id, index] = (
                status.status_id,
                index,
                raw,
                *parsed,
                data.config_version,
            )
    connection.executemany(
        'INSERT INTO special_effect_status_display_rule VALUES (?,?,?,?,?,?,?,?)',
        list(rows.values()),
    )
    connection.execute('DROP TABLE IF EXISTS special_effect_status_config')
    connection.execute(
        'CREATE TABLE special_effect_status_config (status_id INTEGER PRIMARY KEY, config_json TEXT NOT NULL, config_version TEXT NOT NULL)'
    )
    connection.executemany(
        'INSERT INTO special_effect_status_config VALUES (?,?,?)',
        [
            (status_id, raw, data.config_version)
            for status_id, raw in data.status_configs
        ],
    )


__all__ = [
    'CLIENT_EFFECT_ASSETS',
    'ClientEffectData',
    'parse_client_effect_data',
    'replace_client_effect_tables',
]
