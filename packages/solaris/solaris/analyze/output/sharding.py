from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from seerapi_models.build_model import BaseResModel
from solaris.analyze.typing_ import TResModelRequiredId
from solaris.analyze.utils import to_json

if TYPE_CHECKING:
    from .outputter import JsonOutputter

SHARD_BYTES_OVERHEAD = 4096
DEFAULT_MAX_SHARD_BYTES = 1_048_576
SHARDED_FORMAT_VERSION = 'sharded-v1'


def _calc_hash(data: str | bytes) -> str:
    from .outputter import _calc_hash as calc

    return calc(data)


def estimate_dump_bytes(payload: Mapping[str, Any], *, compact: bool = False) -> int:
    """估算经 ``_dump_data`` 写入后的字节大小（含 hash）。"""
    indent = None if compact else 2
    body = dict(payload)
    body['hash'] = _calc_hash(to_json(body, indent=None))
    return len(to_json(body, indent=indent))


def serialize_record(model: BaseModel | Mapping[str, Any]) -> Any:
    if isinstance(model, BaseModel):
        return model.model_dump(by_alias=True)
    return dict(model)


def calc_resource_hash(shard_hashes: Mapping[str, str]) -> str:
    """按分片 id 聚合各分片 file hash，得到资源级数据指纹。"""
    payload = {sid: shard_hashes[sid] for sid in sorted(shard_hashes)}
    return _calc_hash(to_json(payload, indent=None))


def _write_resource_hash_file(
    outputter: JsonOutputter,
    resource_name: str,
    resource_hash: str,
) -> None:
    path = outputter.data_output_dir.joinpath(resource_name, 'resource.hash')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(resource_hash, encoding='utf-8')


def pack_records(
    items: list[tuple[str, Any]],
    max_bytes: int,
    *,
    record_label: str = 'record',
    estimate_shard: Callable[[dict[str, Any]], int] | None = None,
    compact: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """贪心装箱，将键值对拆成多个不超过 ``max_bytes`` 的字典分片。

    Args:
        estimate_shard: 估算分片落盘体积；默认按裸 dict 计算（id 数据分片）。
            索引分片应传入包含 ``format`` / ``mapping_key`` 包装后的估算函数。

    Returns:
        (分片列表, 每个 key 对应的分片 id)
    """
    estimate = estimate_shard or (
        lambda part: estimate_dump_bytes(part, compact=compact)
    )
    budget = max(max_bytes - SHARD_BYTES_OVERHEAD, 1)
    shards: list[dict[str, Any]] = []
    key_to_shard: dict[str, str] = {}
    current: dict[str, Any] = {}

    def flush_current() -> None:
        nonlocal current
        if not current:
            return
        shard_id = f'{len(shards):04d}'
        for key in current:
            key_to_shard[key] = shard_id
        shards.append(current)
        current = {}

    for key, value in sorted(items, key=lambda item: item[0]):
        single = {key: value}
        single_size = estimate(single)
        if single_size > max_bytes:
            warnings.warn(
                f'{record_label} {key!r} serialized size {single_size} bytes '
                f'exceeds shard limit {max_bytes}',
                stacklevel=2,
            )
            flush_current()
            shard_id = f'{len(shards):04d}'
            key_to_shard[key] = shard_id
            shards.append(single)
            continue

        trial = {**current, key: value}
        if current and estimate(trial) > budget:
            flush_current()
            current[key] = value
        else:
            current[key] = value

    flush_current()
    return shards, key_to_shard


def build_name_to_ids_map(
    data: Mapping[int, TResModelRequiredId],
    model: type[BaseResModel],
) -> dict[str, list[int]]:
    """构建 name → id 列表映射（与 ``NamedData`` 一致，同名可对应多个 id）。"""
    from .outputter import get_name_fields

    by_name: dict[str, list[int]] = {}
    for name_field in get_name_fields(model):
        for item in data.values():
            if name := getattr(item, name_field, None):
                name = name.strip()
                ids = by_name.setdefault(name, [])
                if item.id not in ids:
                    ids.append(item.id)
    return by_name


def write_maybe_sharded_index(
    outputter: JsonOutputter,
    resource_name: str,
    index_filename: str,
    payload: dict[str, Any],
    mapping_key: str,
    max_bytes: int,
    *,
    shard_index: bool = True,
) -> None:
    """写入索引文件；若 ``shard_index`` 且体积超限则将映射拆到 ``{stem}/shards/``。"""
    compact = outputter.json_compact
    if not shard_index or estimate_dump_bytes(payload, compact=compact) <= max_bytes:
        outputter._dump_data(payload, Path(resource_name) / index_filename)
        return

    mapping: dict[str, Any] = dict(payload[mapping_key])
    meta = {k: v for k, v in payload.items() if k != mapping_key}

    def estimate_index_shard(part: dict[str, Any]) -> int:
        return estimate_dump_bytes(
            {
                'format': SHARDED_FORMAT_VERSION,
                mapping_key: part,
            },
            compact=compact,
        )

    items = [(str(k), v) for k, v in sorted(mapping.items(), key=lambda x: x[0])]
    index_shards, _ = pack_records(
        items,
        max_bytes,
        record_label=f'{mapping_key} entry',
        estimate_shard=estimate_index_shard,
        compact=compact,
    )

    stem = index_filename.removesuffix('.json')
    shard_meta: dict[str, dict[str, Any]] = {}
    for shard_index_num, shard_mapping in enumerate(index_shards):
        shard_id = f'{shard_index_num:04d}'
        rel_path = f'{stem}/shards/{shard_id}.json'
        shard_payload = {
            'format': SHARDED_FORMAT_VERSION,
            mapping_key: shard_mapping,
        }
        outputter._dump_data(shard_payload, Path(resource_name) / rel_path)
        shard_meta[shard_id] = {
            'path': rel_path,
            'count': len(shard_mapping),
        }

    manifest = {
        'format': SHARDED_FORMAT_VERSION,
        'max_shard_bytes': max_bytes,
        'index_sharded': True,
        'mapping_key': mapping_key,
        'shard_count': len(shard_meta),
        'shards': shard_meta,
        **meta,
    }
    outputter._dump_data(manifest, Path(resource_name) / index_filename)


def write_sharded_resource(
    outputter: JsonOutputter,
    *,
    resource_name: str,
    model: type[BaseResModel],
    data: Mapping[int, TResModelRequiredId],
    output_named_data: bool,
    max_shard_bytes: int,
) -> None:
    """输出 serverless 分片布局（id 分片 + id-index + 可选 name-index）。"""
    from .outputter import is_named_model

    items = [
        (str(res_id), serialize_record(record))
        for res_id, record in sorted(data.items())
    ]
    compact = outputter.json_compact
    data_shards, by_id = pack_records(
        items, max_shard_bytes, record_label='id', compact=compact
    )

    shard_meta: dict[str, dict[str, Any]] = {}
    shard_hashes: dict[str, str] = {}
    for shard_index, shard_records in enumerate(data_shards):
        shard_id = f'{shard_index:04d}'
        rel_path = f'id/shards/{shard_id}.json'
        shard_hashes[shard_id] = outputter._dump_data(
            shard_records, Path(resource_name) / rel_path
        )
        shard_meta[shard_id] = {
            'path': rel_path,
            'count': len(shard_records),
        }

    resource_hash = calc_resource_hash(shard_hashes)
    id_index = {
        'format': SHARDED_FORMAT_VERSION,
        'max_shard_bytes': max_shard_bytes,
        'shard_count': len(data_shards),
        'shards': shard_meta,
        'resource_hash': resource_hash,
        'by_id': by_id,
    }
    write_maybe_sharded_index(
        outputter,
        resource_name,
        'id-index.json',
        id_index,
        'by_id',
        max_shard_bytes,
    )
    _write_resource_hash_file(outputter, resource_name, resource_hash)

    if not output_named_data or not is_named_model(model):
        return

    by_name = build_name_to_ids_map(data, model)
    if not by_name:
        return

    name_index = {
        'format': SHARDED_FORMAT_VERSION,
        'max_shard_bytes': max_shard_bytes,
        'by_name': by_name,
    }
    write_maybe_sharded_index(
        outputter,
        resource_name,
        'name-index.json',
        name_index,
        'by_name',
        max_shard_bytes,
        shard_index=False,
    )
