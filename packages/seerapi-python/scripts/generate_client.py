#!/usr/bin/env python3
"""生成客户端的模型映射、类型别名和类型存根。"""

import argparse
import ast
from copy import deepcopy
from dataclasses import dataclass
import inspect
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import seerapi_models as M
from seerapi_models.build_model import BaseResModel

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PACKAGE_ROOT / 'seerapi'
HEADER = '# 由 scripts/generate_client.py 自动生成，请勿手动修改。\n'
RESOURCE_METHODS = {'get', 'paginated_list', 'list', 'get_by_name'}


@dataclass(frozen=True)
class Resource:
    name: str
    export: str
    model: type[BaseResModel]
    named: bool


def discover_resources(module: ModuleType = M) -> list[Resource]:
    """从模型包的公开导出中查找具体资源类，不依赖客户端生成文件。"""
    resources: dict[str, Resource] = {}
    seen: set[type[BaseResModel]] = set()
    for export in sorted(module.__all__):
        model = getattr(module, export)
        if (
            not inspect.isclass(model)
            or not issubclass(model, BaseResModel)
            or inspect.isabstract(model)
            or model.model_config.get('table', False)
            or model in seen
        ):
            continue
        seen.add(model)
        name = model.resource_name()
        if not isinstance(name, str) or not name:
            raise ValueError(f'{export} has an invalid resource name: {name!r}')
        if name in resources:
            raise ValueError(
                f'Duplicate resource name {name!r}: '
                f'{resources[name].export} and {export}'
            )
        fields = getattr(model, '__name_fields__', ['name'])
        named = any(field in model.model_fields for field in fields)
        resources[name] = Resource(name, export, model, named)
    if not resources or not any(resource.named for resource in resources.values()):
        raise ValueError('Expected resources including at least one named model')
    return sorted(resources.values(), key=lambda resource: resource.name)


def render_typing(resources: list[Resource]) -> str:
    named = [resource for resource in resources if resource.named]
    names = ',\n'.join(repr(resource.name) for resource in resources)
    named_names = ',\n'.join(repr(resource.name) for resource in named)
    named_models = '\n | '.join(f'M.{resource.export}' for resource in named)
    return f"""from typing import Literal, TypeAlias, TypeVar

import seerapi_models as M
from seerapi_models.build_model import BaseResModel
from seerapi_models.common import ResourceRef

NamedModelName: TypeAlias = Literal[
{named_names},
]
ModelName: TypeAlias = Literal[
{names},
]
ModelInstance: TypeAlias = BaseResModel
NamedModelInstance: TypeAlias = (
{named_models}
)
ModelType: TypeAlias = type[ModelInstance]
T_ModelInstance = TypeVar('T_ModelInstance', bound=ModelInstance)
T_NamedModelInstance = TypeVar('T_NamedModelInstance', bound=NamedModelInstance)
ResourceArg: TypeAlias = (
    ModelName | type[T_ModelInstance] | ResourceRef[T_ModelInstance]
)
NamedResourceArg: TypeAlias = (
    NamedModelName | type[T_NamedModelInstance] | ResourceRef[T_NamedModelInstance]
)
"""


def render_model_map(resources: list[Resource]) -> str:
    entries = '\n'.join(
        f'    {resource.name!r}: M.{resource.export},' for resource in resources
    )
    return f"""from seerapi._typing import ModelName as ModelName
from seerapi._typing import ModelType as ModelType
import seerapi_models as M

MODEL_MAP: dict[ModelName, ModelType] = {{
{entries}
}}
"""


def stub_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    node = deepcopy(node)
    # 调用异步生成器会直接得到迭代器，无需 await，因此存根使用普通 def。
    if isinstance(node, ast.AsyncFunctionDef) and any(
        isinstance(child, (ast.Yield, ast.YieldFrom)) for child in ast.walk(node)
    ):
        node = ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=node.type_comment,
        )
    node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
    return ast.unparse(ast.fix_missing_locations(node))


def render_overloads(method: str, resources: list[Resource]) -> str:
    named = method == 'get_by_name'
    variable = 'T_NamedModelInstance' if named else 'T_ModelInstance'
    variants = [
        (f'Literal[{resource.name!r}]', f'M.{resource.export}', False)
        for resource in resources
        if not named or resource.named
    ]
    variants.extend(
        [
            (f'type[{variable}]', variable, False),
            (f'ResourceRef[{variable}]', variable, True),
        ]
    )
    signatures = []
    for argument, result, reference in variants:
        if method == 'get':
            params = 'id: int | None = None' if reference else 'id: int'
        elif method == 'paginated_list':
            params, result = 'page_info: PageInfo', f'PagedResponse[{result}]'
        elif method == 'list':
            params, result = '*, expand: bool = True', f'AsyncIterator[{result}]'
        else:
            params, result = 'name: str', f'NamedData[{result}]'
        prefix = '' if method == 'list' else 'async '
        signatures.append(
            f'@overload\n{prefix}def {method}('
            f'self, resource_name: {argument}, {params}) -> {result}: ...'
        )
    return '\n'.join(signatures)


def render_client(resources: list[Resource], source: str) -> str:
    tree = ast.parse(source)
    client = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == 'SeerAPI'
    )
    imports = """from collections.abc import AsyncIterator
from typing import Literal, overload
from typing_extensions import Self

from hishel.httpx import AsyncCacheClient
from httpx import URL
from httpx._urls import QueryParams

from seerapi._models import PagedResponse, PageInfo
from seerapi._typing import ModelName, ResourceArg, T_ModelInstance, T_NamedModelInstance
import seerapi_models as M
from seerapi_models.common import NamedData, ResourceRef
"""
    helpers = [
        stub_function(node)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    members = []
    initializer = next(
        node
        for node in client.body
        if isinstance(node, ast.FunctionDef) and node.name == '__init__'
    )
    for node in ast.walk(initializer):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Attribute)
            and isinstance(node.target.value, ast.Name)
            and node.target.value.id == 'self'
        ):
            members.append(f'{node.target.attr}: {ast.unparse(node.annotation)}')
    members.append('_client: AsyncCacheClient')
    for node in client.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            members.append(
                render_overloads(node.name, resources)
                if node.name in RESOURCE_METHODS
                else stub_function(node)
            )
    body = '\n'.join(
        '    ' + line for member in members for line in member.splitlines()
    )
    return imports + '\n' + '\n\n'.join(helpers) + '\n\nclass SeerAPI:\n' + body + '\n'


def render_outputs(resources: list[Resource], source: str) -> dict[str, bytes]:
    contents = {
        '_typing.py': render_typing(resources),
        '_model_map.py': render_model_map(resources),
        '_client.pyi': render_client(resources, source),
    }
    outputs = {}
    for name, content in contents.items():
        # 先在内存中完成所有文件的格式化，避免失败时只更新了部分文件。
        result = subprocess.run(
            [sys.executable, '-m', 'ruff', 'format', '--stdin-filename', name, '-'],
            input=(HEADER + content).encode('utf-8'),
            capture_output=True,
            cwd=PACKAGE_ROOT,
            check=True,
        )
        outputs[name] = result.stdout.replace(b'\r\n', b'\n')
    return outputs


def update_outputs(outputs: dict[str, bytes], directory: Path, *, check: bool) -> int:
    changed = [
        name
        for name, content in outputs.items()
        if not (directory / name).exists() or (directory / name).read_bytes() != content
    ]
    for name in changed:
        if not check:
            (directory / name).write_bytes(outputs[name])
        print(f'{"Out of date" if check else "Updated"}: {directory / name}')  # noqa: T201
    return int(check and bool(changed))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--check', action='store_true', help='Check without writing files'
    )
    args = parser.parse_args()
    resources = discover_resources()
    outputs = render_outputs(resources, (OUTPUT_DIR / '_client.py').read_text('utf-8'))
    return update_outputs(outputs, OUTPUT_DIR, check=args.check)


if __name__ == '__main__':
    raise SystemExit(main())
