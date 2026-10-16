from datetime import timedelta

import pytest

from solaris.analyze.analyzers.activity import ActivityAnalyzer
from solaris.utils import parse_unity_datetime


def test_activity_time_uses_china_standard_time() -> None:
    value = parse_unity_datetime('2023_01_13 00:00:00')
    assert value.utcoffset() == timedelta(hours=8)
    assert value.isoformat() == '2023-01-13T00:00:00+08:00'


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('2026_11_05 24:00:00', '2026-11-06T00:00:00+08:00'),
        ('2026_1_31 24:00:00', '2026-02-01T00:00:00+08:00'),
        ('2026_12_31 24:00:00', '2027-01-01T00:00:00+08:00'),
        ('2024_02_28 24:00:00', '2024-02-29T00:00:00+08:00'),
        ('2024_02_29 24:00:00', '2024-03-01T00:00:00+08:00'),
        ('2026_02_28 24:00:00', '2026-03-01T00:00:00+08:00'),
        ('2026_1_2 23:59:59', '2026-01-02T23:59:59+08:00'),
    ],
)
def test_unity_time_boundaries(raw: str, expected: str) -> None:
    assert parse_unity_datetime(raw).isoformat() == expected


@pytest.mark.parametrize(
    'raw',
    [
        '2026_11_05 24:01:00',
        '2026_11_05 24:00:01',
        '2026_11_05 25:00:00',
        '2026_02_29 24:00:00',
        '2026_11_31 24:00:00',
        '2026_11_05 -1:00:00',
        '',
        '2026_11_05 24:00:00junk',
    ],
)
def test_invalid_unity_time_still_fails(raw: str) -> None:
    with pytest.raises(ValueError, match=r'.+'):
        parse_unity_datetime(raw)


def test_real_activity_592_and_required_time_failure(monkeypatch) -> None:
    item = {
        'id': 592,
        'labelName': '10万现金激励',
        'beginning': '2026_10_16 10:00:00',
        'ending': '2026_11_05 24:00:00',
        'type': 9,
        'isShow': 1,
        'sorting': 5,
    }
    analyzer = object.__new__(ActivityAnalyzer)
    monkeypatch.setattr(analyzer, '_get_data', lambda *_: {'item': [item]})
    results = analyzer.analyze()
    assert results[0].data[592].end_time.isoformat() == '2026-11-06T00:00:00+08:00'
    item['ending'] = '2026_11_05 24:01:00'
    with pytest.raises(
        ValueError, match=r'ActivityCenter.json: item=592, field=ending'
    ) as caught:
        analyzer.analyze()
    assert caught.value.__cause__ is not None
