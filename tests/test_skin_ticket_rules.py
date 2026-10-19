from pathlib import Path
import sqlite3
import sys

import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from release_config_tables import replace_skin_ticket_rules
from release_contract import GENERATED_RELEASE_TABLES


@pytest.mark.parametrize('value', [10, 25])
def test_explicit_scope_name_and_value_preserve_source(value: int) -> None:
    description = (
        f'通过“风尚月历”获得，可在幸运橱窗中使用，每张测试券可抵扣{value}钻石。'
    )
    with sqlite3.connect(':memory:') as connection:
        connection.executescript("""
            CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT, desc TEXT);
            CREATE TABLE skin_store_price (ticket_id INTEGER);
            INSERT INTO skin_store_price VALUES (1), (1);
        """)
        connection.execute('INSERT INTO item VALUES (1, ?, ?)', ('测试券', description))
        assert replace_skin_ticket_rules(connection) == 1
        assert connection.execute('SELECT * FROM skin_ticket_rule').fetchall() == [
            (
                1,
                value,
                'item.desc:lucky_window_per_ticket_diamonds_v1',
                description,
            )
        ]
        connection.execute("UPDATE item SET desc = '售价10钻石'")
        assert replace_skin_ticket_rules(connection) == 0
        assert connection.execute('SELECT * FROM skin_ticket_rule').fetchall() == []
    assert 'skin_ticket_rule' in GENERATED_RELEASE_TABLES


@pytest.mark.parametrize(
    'description',
    [
        '售价10钻石',
        '通过“月历”获得，可在其他商店中使用，每张测试券可抵扣10钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张其他券可抵扣10钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券最多可抵扣10钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券可抵扣0钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券可抵扣-10钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券可抵扣10钻石。满100钻可用。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券有概率可抵扣10钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券可抵扣10钻石或20钻石。',
        '通过“月历”获得，可在幸运橱窗中使用，每张测试券可抵扣9999999999999999999999钻石。',
        '每张测试券可抵扣10钻石。',
        '',
    ],
)
def test_unproven_or_conditional_descriptions_emit_no_rule(description: str) -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.executescript("""
            CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT, desc TEXT);
            CREATE TABLE skin_store_price (ticket_id INTEGER);
            INSERT INTO skin_store_price VALUES (1);
        """)
        connection.execute('INSERT INTO item VALUES (1, ?, ?)', ('测试券', description))
        assert replace_skin_ticket_rules(connection) == 0
