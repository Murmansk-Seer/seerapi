from pathlib import Path
import struct
import sys
from types import SimpleNamespace

SCRIPTS = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import preview_window_dll as parser


def _image(start: str, end: str) -> object:
    name = b'ActivityListPreviewPanel\0'
    type_data = bytearray(16)
    struct.pack_into('<I', type_data, 4, 1)
    strings = SimpleNamespace(__data__=b'\0' + name)
    panel = SimpleNamespace(
        TypeNamespace='module.activityListPreview',
        struct=SimpleNamespace(FieldList_Index=1, MethodList_Index=1),
    )
    next_type = SimpleNamespace(
        struct=SimpleNamespace(FieldList_Index=3, MethodList_Index=2)
    )
    types = SimpleNamespace(
        _table_data=bytes(type_data), _strings_heap=strings,
        _strings_offset_size=4, row_size=8, num_rows=2,
        rows=[panel, next_type],
    )
    fields = SimpleNamespace(rows=[
        SimpleNamespace(Name='s_T1StartTime'),
        SimpleNamespace(Name='s_T1EndTime'),
    ])
    methods = SimpleNamespace(rows=[SimpleNamespace(Name='.cctor', Rva=100)])
    il = (
        b'\x72' + struct.pack('<I', 0x70000001)
        + b'\x80' + struct.pack('<I', 0x04000001)
        + b'\x72' + struct.pack('<I', 0x70000002)
        + b'\x80' + struct.pack('<I', 0x04000002)
        + b'\x2a'
    )
    body = bytes([(len(il) << 2) | 2]) + il
    return SimpleNamespace(
        net=SimpleNamespace(
            mdtables=SimpleNamespace(TypeDef=types, Field=fields, MethodDef=methods),
            user_strings=SimpleNamespace(get=lambda token: {1: start, 2: end}[token]),
        ),
        get_data=lambda _rva, length: body[:length],
    )


def test_reads_dates_assigned_to_official_preview_fields(monkeypatch) -> None:
    monkeypatch.setattr(parser.dnfile, 'dnPE', lambda **_kwargs: _image(
        '2026-09-24 10:00:00', '2026-10-02 00:00:00'
    ))
    window = parser.parse_preview_window(b'fixture')
    assert window.cycle_id == '2026-09-24T10:00:00+08:00'
    assert int(window.end.timestamp()) > int(window.start.timestamp())


def test_rejects_invalid_window(monkeypatch) -> None:
    monkeypatch.setattr(parser.dnfile, 'dnPE', lambda **_kwargs: _image(
        '2026-10-02 00:00:00', '2026-09-24 10:00:00'
    ))
    import pytest

    with pytest.raises(ValueError, match='invalid'):
        parser.parse_preview_window(b'fixture')
