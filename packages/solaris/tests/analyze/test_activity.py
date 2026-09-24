from datetime import timedelta

from solaris.analyze.analyzers.activity import parse_activity_time


def test_activity_time_uses_china_standard_time() -> None:
    value = parse_activity_time('2023_01_13 00:00:00')
    assert value.utcoffset() == timedelta(hours=8)
    assert value.isoformat() == '2023-01-13T00:00:00+08:00'
