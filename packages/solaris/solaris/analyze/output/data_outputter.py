"""JSON and database output implementations for analyzed Seer data."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Protocol, overload

from pydantic import BaseModel
from tqdm import tqdm

from seerapi_models.common import NamedData, ResourceRef
from seerapi_models.metadata import ApiMetadata
from solaris.analyze.typing_ import (
    AnalyzeResult,
    JsonFormat,
    NameGenerator,
    TResModelRequiredId,
)
from solaris.analyze.utils import to_json
from solaris.utils import join_url

from .db import DBManager
from .json_format import resolve_json_format
from .output_helpers import DataMap, calc_hash, generate_api_resource_list
from .sharding import DEFAULT_MAX_SHARD_BYTES


class DataOutputterProtocol(Protocol):
    """Common contract for analyzed data sinks."""

    def run(self, results: Sequence[AnalyzeResult]) -> None: ...


class JsonOutputter(DataOutputterProtocol):
    """Write analyzed resources as JSON documents."""

    def __init__(
        self,
        *,
        metadata: ApiMetadata,
        base_output_dir: str | Path = '.',
        data_output_dir: str | Path,
        base_data_url: str | None = None,
        shard_max_bytes: int = DEFAULT_MAX_SHARD_BYTES,
    ) -> None:
        self.metadata = metadata
        self.shard_max_bytes = shard_max_bytes
        version = metadata.api_version
        self.data_url = base_data_url or join_url(
            metadata.api_url, version, str(data_output_dir)
        )
        ResourceRef.base_data_url = self.data_url
        self.data_output_dir = Path().joinpath(
            base_output_dir,
            version,
            data_output_dir,
        )
        self.data_output_dir.mkdir(parents=True, exist_ok=True)
        self.json_compact = False

    def _dump_data(
        self,
        data: Any,
        path: Path | str,
        *,
        compact: bool | None = None,
    ) -> str:
        if isinstance(data, BaseModel):
            payload: MutableMapping[str, Any] = data.model_dump(by_alias=True)
        elif isinstance(data, MutableMapping):
            payload = dict(data)
        else:
            raise ValueError(f'Invalid data type: {type(data)}')
        indent = None if (self.json_compact if compact is None else compact) else 2
        file_hash = calc_hash(to_json(payload, indent=None))
        payload['hash'] = file_hash
        output_path = self.data_output_dir.joinpath(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(to_json(payload, indent=indent))
        return file_hash

    def _output_merged_json(self, resource_name: str, data: Any) -> None:
        self._dump_data(data, Path(resource_name) / 'id.json')

    def _output_merged_named_json(
        self,
        name_data: Mapping[str, NamedData[TResModelRequiredId]],
        resource_name: str,
    ) -> None:
        self._dump_data(name_data, Path(resource_name) / 'name.json')

    def _generate_name_data(
        self,
        data: DataMap[TResModelRequiredId],
        *,
        name_generator: NameGenerator,
    ) -> Mapping[str, NamedData[TResModelRequiredId]]:
        name_data: defaultdict[str, NamedData[TResModelRequiredId]] = defaultdict(
            lambda: NamedData(data={})
        )
        for id_, model in data.items():
            if name := name_generator(model):
                name_data[name.strip()].data[id_] = model
        return name_data

    def _output_named_json(
        self,
        name_data: Mapping[str, NamedData[TResModelRequiredId]],
        resource_name: str,
    ) -> None:
        for name, res_data in name_data.items():
            self._dump_data(res_data, Path(resource_name, name, 'index.json'))

    def _output_individual_json(
        self,
        data: DataMap[TResModelRequiredId],
        resource_name: str,
    ) -> None:
        self._output_api_resource_list(data, resource_name)
        for res_id, res_data in data.items():
            self._dump_data(res_data, Path(resource_name, str(res_id), 'index.json'))

    def _output_api_resource_list(
        self,
        data: DataMap[TResModelRequiredId],
        resource_name: str,
    ) -> None:
        self._dump_data(
            generate_api_resource_list(data),
            Path(resource_name, 'index.json'),
        )

    def _process_single_result(
        self,
        result: AnalyzeResult[TResModelRequiredId],
        *,
        json_format: JsonFormat,
        output_name_data: bool,
    ) -> tuple[str, str] | None:
        if result.output_mode not in ('json', 'all'):
            return None
        model = result.model
        resource_name = model.resource_name()
        resolve_json_format(json_format).write_resource(
            self,
            resource_name=resource_name,
            model=model,
            data=result.data,
            output_named_data=output_name_data,
        )
        return resource_name, join_url(self.data_url, resource_name)

    def _output_metadata(self) -> None:
        self._dump_data(self.metadata, 'metadata.json')

    def _output_root_index(self, index_data: dict[str, str]) -> None:
        self._dump_data(index_data, 'index.json')

    def run(
        self,
        results: Sequence[AnalyzeResult],
        *,
        json_format: JsonFormat = 'split',
        output_named_data: bool = False,
    ) -> None:
        self.json_compact = json_format == 'sharded'
        root_index_data: dict[str, str] = {}
        for result in (progress := tqdm(results, leave=False)):
            resource_name = result.model.resource_name()
            progress.set_description(
                f'正在输出 JSON 数据 | 输出{resource_name}',
                refresh=True,
            )
            result_info = self._process_single_result(
                result,
                json_format=json_format,
                output_name_data=output_named_data,
            )
            if result_info is not None:
                resource_name, resource_url = result_info
                root_index_data[resource_name] = resource_url
        self._output_metadata()
        self._output_root_index(root_index_data)


class DBOutputter(DataOutputterProtocol):
    """Write analyzed resources through the configured database manager."""

    @overload
    def __init__(self, metadata: ApiMetadata, *, db_manager: DBManager) -> None: ...

    @overload
    def __init__(
        self,
        metadata: ApiMetadata,
        *,
        db_url: str,
        echo: bool = False,
        **kwargs: Any,
    ) -> None: ...

    def __init__(self, metadata: ApiMetadata, **kwargs: Any) -> None:
        self.metadata = metadata
        if 'db_manager' in kwargs:
            self.db_manager = kwargs['db_manager']
        elif 'db_url' in kwargs and 'echo' in kwargs:
            self.db_manager = DBManager(**kwargs)
        else:
            raise ValueError('Invalid arguments')

    def init(self) -> None:
        if not self.db_manager.initialized:
            self.db_manager.init()

    @property
    def initialized(self) -> bool:
        return self.db_manager.initialized

    def run(self, results: Sequence[AnalyzeResult]) -> None:
        if not self.initialized:
            raise RuntimeError('Database not initialized')
        for result in (progress := tqdm(results, leave=False)):
            name = result.model.resource_name()
            progress.set_description(
                f'正在输出数据库数据 | 输出{name}',
                refresh=True,
            )
            if result.output_mode not in ('db', 'all'):
                continue
            with self.db_manager.get_session() as session:
                from .db import write_result_to_db

                write_result_to_db(session, result.data)
        with self.db_manager.get_session() as session:
            session.add(self.metadata.to_orm())
            session.commit()
