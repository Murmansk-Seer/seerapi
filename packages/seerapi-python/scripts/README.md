# 更新客户端类型

新增模型后，客户端需要知道资源名对应哪个模型，编辑器也需要知道调用方法会返回什么类型。`generate_client.py` 会一起更新这些信息，不用分别维护三份文件：

- `seerapi/_model_map.py`：资源名与模型类的对应关系。
- `seerapi/_typing.py`：资源名称、模型和方法参数的类型别名。
- `seerapi/_client.pyi`：供编辑器补全和类型检查使用的方法签名。

## 怎么运行

新增、删除模型，修改资源名、名称字段或客户端方法签名后，在仓库根目录运行：

```sh
uv run --package seerapi python packages/seerapi-python/scripts/generate_client.py
```

脚本会直接更新上面的三份文件。查看改动后，把它们和相关代码一起提交即可。请修改模型或生成脚本，再重新生成，不要直接改这三份文件。

只想确认文件有没有更新，可以加上 `--check`：

```sh
uv run --package seerapi python packages/seerapi-python/scripts/generate_client.py --check
```

没有输出表示文件已是最新；如果有文件缺失或需要更新，脚本会列出路径并以状态码 1 退出，不会改写文件。

运行时需要 Ruff，它已包含在工作区的开发依赖中。如果从其他目录运行，请使用脚本的绝对路径，生成文件仍会写回客户端包。

## 模型没出现在结果里？

先检查它是否已导出到 `seerapi_models.__all__`。脚本只收集具体的 `BaseResModel` 子类，抽象类和 ORM 表模型不会加入客户端。同一个类导出多次只算一次；两个不同的类使用相同资源名时，脚本会报错，需要先解决命名冲突。

`get_by_name` 是否支持某个模型，取决于模型有没有名称字段：默认查找 `name`，也可以通过 `__name_fields__` 指定其他字段。指定的字段中只要有一个存在，就会生成对应的类型声明。这与 Solaris 的判断方式一致。

修改客户端方法时也要留意：普通方法签名会从 `_client.py` 中读取，但 `get`、`paginated_list`、`list` 和 `get_by_name` 的重载参数写在生成脚本里。调整这些方法的参数后，需要同步修改脚本。
