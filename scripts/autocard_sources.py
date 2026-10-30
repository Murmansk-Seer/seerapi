# SPDX-License-Identifier: MIT
"""Source loading and normalization for published Autocard JSON assets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from solaris.parse.parsers.autocard_buff import AutocardBuffParser
from solaris.parse.parsers.autocard_content import AutocardContentParser
from solaris.parse.parsers.autocard_nature import AutocardNatureParser
from solaris.parse.parsers.autocard_role import AutocardRoleParser

AUTOCARD_PARSERS = {
    'autocardContent.json': AutocardContentParser,
    'autocardNature.json': AutocardNatureParser,
    'autocardRole.json': AutocardRoleParser,
    'autocardBuff.json': AutocardBuffParser,
}
AUTOCARD_TEXT_ASSETS = frozenset(
    parser.source_config_filename() for parser in AUTOCARD_PARSERS.values()
)
_OFFICIAL_FIELD_NAMES = {
    'buff_id': 'BuffId',
    'buff_param': 'BuffParam',
    'count_num': 'CountNum',
    'count_type': 'CountType',
    'display': 'Display',
    'card_txt': 'cardTxt',
    'compose_to': 'composeTo',
    'headpic_id': 'headpicID',
    'is_use': 'isUse',
    'pic_id': 'picID',
    'skill_cost_num': 'skillCostNum',
    'skill_game_limit': 'skillGameLimit',
    'skill_id': 'skillID',
    'skill_name': 'skillName',
    'skill_round_limit': 'skillRoundLimit',
    'skill_txt': 'skillTxt',
    'skill_type': 'skillType',
    'skill_upgrade': 'skillUpgrade',
    'is_bf_battle_effect': 'IsBfBattleEffect',
    'is_cold_wave_effect': 'IsColdWaveEffect',
    'is_death_effect': 'IsDeathEffect',
    'is_growth_effect': 'IsGrowthEffect',
    'is_place_effect': 'IsPlaceEffect',
    'buff_des': 'buffDes',
    'buff_object': 'buffObject',
    'effect_icon': 'effectIcon',
}


def normalize_autocard_row(
    row: dict[str, object], *, filename: str = ''
) -> dict[str, object]:
    """Keep the published raw field contract stable across parser formats."""
    result: dict[str, object] = {}
    for key, value in row.items():
        canonical = _OFFICIAL_FIELD_NAMES.get(key, key)
        if filename == 'autocardBuff.json' and key in {
            'buff_param',
            'BuffParam',
            'buffParam',
        }:
            canonical = 'buffParam'
        if canonical in result and result[canonical] != value:
            raise ValueError(f'conflicting Autocard field aliases: {canonical}')
        result[canonical] = value
    return result


def parse_autocard_json(filename: str, payload: bytes) -> dict[str, object]:
    parser = AUTOCARD_PARSERS[filename]()
    raw = parser.parse(payload)
    rows = json_data_rows(dict(raw))
    if not rows:
        raise ValueError(f'official Autocard source is empty: {filename}')
    ids = [row.get('id') for row in rows]
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in ids
    ):
        raise ValueError(f'invalid official Autocard IDs: {filename}')
    if len(set(ids)) != len(ids):
        raise ValueError(f'duplicate official Autocard IDs: {filename}')
    return {'data': [normalize_autocard_row(row, filename=filename) for row in rows]}


JsonLoader = Callable[[str], tuple[dict[str, object], str]]


@dataclass(frozen=True, slots=True)
class AutocardData:
    cards: list[dict[str, object]]
    roles: list[dict[str, object]]
    natures: list[dict[str, object]]
    buffs: list[dict[str, object]]
    source: str


def load_autocard_data(
    load_json: JsonLoader,
    *,
    content_file: str,
    nature_file: str,
    role_file: str,
    buff_file: str,
) -> AutocardData:
    """Load the four official Autocard exports through one source boundary."""

    content_json, content_source = load_json(content_file)
    nature_json, nature_source = load_json(nature_file)
    role_json, role_source = load_json(role_file)
    buff_json, buff_source = load_json(buff_file)
    return AutocardData(
        cards=[
            normalize_autocard_row(row, filename='autocardContent.json')
            for row in json_data_rows(content_json)
        ],
        roles=[
            normalize_autocard_row(row, filename='autocardRole.json')
            for row in json_data_rows(role_json)
        ],
        natures=[
            normalize_autocard_row(row, filename='autocardNature.json')
            for row in json_data_rows(nature_json)
        ],
        buffs=[
            normalize_autocard_row(row, filename='autocardBuff.json')
            for row in json_data_rows(buff_json)
        ],
        source='\n'.join(
            sorted({buff_source, content_source, nature_source, role_source})
        ),
    )


def json_data_rows(raw: dict[str, object]) -> list[dict[str, object]]:
    """Return only object rows from the common Unity JSON ``data`` envelope."""

    rows = raw.get('data', [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]
