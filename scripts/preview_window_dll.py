"""Read the official preview display window from the game's .NET assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import struct
from typing import Any, cast
from zoneinfo import ZoneInfo

import dnfile

PANEL_NAMESPACE = 'module.activityListPreview'
PANEL_NAME = 'ActivityListPreviewPanel'
START_FIELD = 's_T1StartTime'
END_FIELD = 's_T1EndTime'
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?$')
SHANGHAI = ZoneInfo('Asia/Shanghai')


@dataclass(frozen=True)
class PreviewWindow:
    start: datetime
    end: datetime

    @property
    def cycle_id(self) -> str:
        return self.start.isoformat(timespec='seconds')


def _row_for_name(table: object, name: str) -> int:
    # dnfile's lazy tables avoid decoding the assembly's ~145k method rows.
    data = table._table_data  # type: ignore[attr-defined]
    heap = table._strings_heap.__data__  # type: ignore[attr-defined]
    index = heap.find(name.encode('utf-8') + b'\0')
    if index < 0:
        raise ValueError(f'DLL is missing {name}')
    width = table._strings_offset_size  # type: ignore[attr-defined]
    row_size = table.row_size  # type: ignore[attr-defined]
    wanted = index.to_bytes(width, 'little')
    for row in range(table.num_rows):  # type: ignore[attr-defined]
        offset = row * row_size
        if data[offset + 4 : offset + 4 + width] == wanted:
            return row
    raise ValueError(f'DLL has no metadata row for {name}')


def _method_il(image: object, rva: int) -> bytes:
    header = image.get_data(rva, 12)  # type: ignore[attr-defined]
    if not header:
        raise ValueError('DLL method body is empty')
    if header[0] & 3 == 2:
        header_size, code_size = 1, header[0] >> 2
    elif header[0] & 3 == 3:
        header_size = (int.from_bytes(header[:2], 'little') >> 12) * 4
        code_size = int.from_bytes(header[4:8], 'little')
    else:
        raise ValueError('DLL method header is invalid')
    if code_size > 4096 or header_size < 1:
        raise ValueError('DLL preview initializer is unexpectedly large')
    body = image.get_data(rva, header_size + code_size)  # type: ignore[attr-defined]
    return body[header_size:]


def _assigned_date(image: object, il: bytes, field_row: int) -> datetime:
    assignment = il.find(b'\x80' + struct.pack('<I', 0x04000000 | field_row))
    if assignment < 0:
        raise ValueError('DLL preview field has no initializer')
    dates: list[str] = []
    for pos in range(assignment):
        if il[pos] != 0x72 or pos + 5 > assignment:
            continue
        token = struct.unpack_from('<I', il, pos + 1)[0]
        if token >> 24 != 0x70:
            continue
        value = image.net.user_strings.get(token & 0xFFFFFF)  # type: ignore[attr-defined]
        if value is not None and DATE_PATTERN.fullmatch(str(value)):
            dates.append(str(value))
    if not dates:
        raise ValueError('DLL preview field has no date literal')
    return datetime.fromisoformat(dates[-1]).replace(tzinfo=SHANGHAI)


def parse_preview_window(dll: bytes) -> PreviewWindow:
    """Fail closed if the official class or both assigned dates cannot be proved."""
    image = dnfile.dnPE(data=dll, clr_lazy_load=True)
    if image.net is None:
        raise ValueError('Not a .NET game logic DLL')
    types = cast(Any, image.net.mdtables.TypeDef)
    fields = cast(Any, image.net.mdtables.Field)
    methods = cast(Any, image.net.mdtables.MethodDef)
    if types is None or fields is None or methods is None:
        raise ValueError('DLL metadata tables are incomplete')
    type_index = _row_for_name(types, PANEL_NAME)
    panel = types.rows[type_index]
    if str(panel.TypeNamespace) != PANEL_NAMESPACE:
        raise ValueError('Preview panel namespace differs from the expected class')
    next_type = types.rows[type_index + 1]
    field_rows = {
        str(fields.rows[index - 1].Name): index
        for index in range(panel.struct.FieldList_Index, next_type.struct.FieldList_Index)
    }
    if START_FIELD not in field_rows or END_FIELD not in field_rows:
        raise ValueError('DLL preview window fields are missing')
    initializers = [
        methods.rows[index - 1]
        for index in range(panel.struct.MethodList_Index, next_type.struct.MethodList_Index)
        if str(methods.rows[index - 1].Name) == '.cctor'
    ]
    if len(initializers) != 1:
        raise ValueError('DLL preview panel has no unique static initializer')
    il = _method_il(image, initializers[0].Rva)
    start = _assigned_date(image, il, field_rows[START_FIELD])
    end = _assigned_date(image, il, field_rows[END_FIELD])
    if not start < end or end - start > timedelta(days=60):
        raise ValueError('DLL preview display window is invalid')
    return PreviewWindow(start=start, end=end)
