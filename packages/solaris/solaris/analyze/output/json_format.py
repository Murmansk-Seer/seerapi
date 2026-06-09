from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar

from seerapi_models.build_model import BaseResModel
from seerapi_models.common import NamedData
from solaris.analyze.typing_ import TResModelRequiredId

if TYPE_CHECKING:
    from .outputter import JsonOutputter

_JSON_FORMATS: dict[str, type[JsonOutputFormat]] = {}


def register_json_format(cls: type[JsonOutputFormat]) -> type[JsonOutputFormat]:
    _JSON_FORMATS[cls.name] = cls
    return cls


def resolve_json_format(
    name: str | type[JsonOutputFormat],
) -> type[JsonOutputFormat]:
    if isinstance(name, str):
        try:
            return _JSON_FORMATS[name]
        except KeyError as exc:
            known = ', '.join(sorted(_JSON_FORMATS))
            raise ValueError(
                f'Unknown JSON output format {name!r}; known formats: {known}'
            ) from exc
    if issubclass(name, JsonOutputFormat) and name.name in _JSON_FORMATS:
        return name
    raise ValueError(f'Unregistered JSON output format: {name!r}')


def json_format_names() -> tuple[str, ...]:
    return tuple(sorted(_JSON_FORMATS))


class JsonOutputFormat(ABC):
    """JSON 输出子模式基类；新增子模式时继承并使用 ``@register_json_format`` 注册。"""

    name: ClassVar[str]

    @classmethod
    @abstractmethod
    def write_resource(
        cls,
        outputter: JsonOutputter,
        *,
        resource_name: str,
        model: type[BaseResModel],
        data: Mapping[int, TResModelRequiredId],
        output_named_data: bool,
    ) -> None:
        raise NotImplementedError


def _collect_name_data(
    outputter: JsonOutputter,
    model: type[BaseResModel],
    data: Mapping[int, TResModelRequiredId],
) -> dict[str, NamedData[TResModelRequiredId]]:
    from .outputter import get_name_fields

    merged_name_data: dict[str, NamedData[TResModelRequiredId]] = {}
    for name_field in get_name_fields(model):

        def _name_generator(
            m: TResModelRequiredId, field: str = name_field
        ) -> str | None:
            return getattr(m, field, None)

        name_data = outputter._generate_name_data(data, name_generator=_name_generator)
        merged_name_data.update(name_data)
    return merged_name_data


def _write_named_data(
    outputter: JsonOutputter,
    *,
    model: type[BaseResModel],
    data: Mapping[int, TResModelRequiredId],
    resource_name: str,
    output_named_data: bool,
    merged: bool,
) -> None:
    from .outputter import is_named_model

    if not output_named_data or not is_named_model(model):
        return

    name_data = _collect_name_data(outputter, model, data)
    if merged:
        outputter._output_merged_named_json(name_data, resource_name)
    else:
        outputter._output_named_json(name_data, resource_name)


@register_json_format
class SplitJsonOutputFormat(JsonOutputFormat):
    name = 'split'

    @classmethod
    def write_resource(
        cls,
        outputter: JsonOutputter,
        *,
        resource_name: str,
        model: type[BaseResModel],
        data: Mapping[int, TResModelRequiredId],
        output_named_data: bool,
    ) -> None:
        outputter._output_individual_json(data, resource_name)
        _write_named_data(
            outputter,
            model=model,
            data=data,
            resource_name=resource_name,
            output_named_data=output_named_data,
            merged=False,
        )


@register_json_format
class MergedJsonOutputFormat(JsonOutputFormat):
    name = 'merged'

    @classmethod
    def write_resource(
        cls,
        outputter: JsonOutputter,
        *,
        resource_name: str,
        model: type[BaseResModel],
        data: Mapping[int, TResModelRequiredId],
        output_named_data: bool,
    ) -> None:
        outputter._output_merged_json(resource_name, data)
        _write_named_data(
            outputter,
            model=model,
            data=data,
            resource_name=resource_name,
            output_named_data=output_named_data,
            merged=True,
        )


@register_json_format
class ShardedJsonOutputFormat(JsonOutputFormat):
    name = 'sharded'

    @classmethod
    def write_resource(
        cls,
        outputter: JsonOutputter,
        *,
        resource_name: str,
        model: type[BaseResModel],
        data: Mapping[int, TResModelRequiredId],
        output_named_data: bool,
    ) -> None:
        from .sharding import write_sharded_resource

        write_sharded_resource(
            outputter,
            resource_name=resource_name,
            model=model,
            data=data,
            output_named_data=output_named_data,
            max_shard_bytes=outputter.shard_max_bytes,
        )
