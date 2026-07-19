---
name: seerapi-cli
description: 通过 seerapi CLI 查询赛尔号游戏数据（精灵、技能、装备等）。在用户询问 SeerAPI 数据、需要查 pet/skill/item、或提到 seerapi 命令时使用。教 agent 先 resources 再 describe/get/list，并控制 --fields 与 --limit。
---

# SeerAPI CLI

使用已安装的 `seerapi` 命令查询赛尔号游戏数据。stdout 为 JSON，stderr 为错误 JSON。

**前置条件**：`pip install seerapi`，且 `seerapi --version` 可用。

将本 skill 目录复制到你使用的 AI agent 的 skills 目录，或：

```bash
seerapi skill install --target <your-agent-skills-dir>
# 或设置环境变量：SEERAPI_SKILL_DIR=<your-agent-skills-dir>
```

查看源路径：`seerapi skill path`

## 适用场景

| 场景 | 做法 |
|------|------|
| 查资源、列表、按名称查 | `seerapi` CLI |
| 写 Python 集成 | `from seerapi import SeerAPI` |
| 完整 OpenAPI 契约 | https://api.seerapi.com |

## 标准工作流

1. `seerapi resources` — 发现资源名与 `supports_name_lookup`
2. `seerapi describe <resource> --fields ...` — 看字段（默认 `--scope item`）
3. 按情况查询：
   - 已知 ID → `seerapi get <resource> <id> [--fields]`
   - 浏览列表 → `seerapi list <resource> --limit N [--fields]`
   - 已知中文名且 `supports_name_lookup=true` → `seerapi get-by-name <resource> "<name>"`

## 硬性规则

1. **禁止猜测** resource 名；不确定时先 `resources`，失败时读 stderr 的 `did_you_mean`
2. `describe` 默认 `--scope item`（实例字段）；`--scope list` 只看分页结构；`--scope name` 仅 NamedModel
3. `list` 默认单页 `limit=20`；禁止无上限翻页；用输出中的 `next` 翻页
4. 大对象必须加 `--fields`；仅人类阅读时用 `--pretty`
5. 中文名称加引号：`seerapi get-by-name skill "虚妄幻境"`

## 命令速查

| 命令 | 用途 |
|------|------|
| `resources` | 全部资源 + `supports_name_lookup` |
| `describe <r> [--scope item\|list\|name] [--fields]` | JSON Schema |
| `get <r> <id> [--fields]` | 单条 by ID |
| `list <r> [--offset] [--limit] [--expand] [--fields]` | 单页列表 |
| `get-by-name <r> <name>` | 按名称（返回 id→对象 字典） |
| `skill [install\|path]` | 查看或安装 agent skill |

全局选项：`--hostname` `--scheme` `--version-path` `--pretty`；环境变量 `SEERAPI_HOSTNAME` / `SEERAPI_SCHEME`。

## Token 优化

- `describe` / `get` / `list` 均支持 `--fields`，优先只取需要的字段
- `list` 保持 `--limit 20` 或更小
- 默认 compact JSON，不加 `--pretty`
- `get-by-name` 可能返回多个同名 id，用 `power` 等字段甄别

## 错误处理

| exit code | 含义 | 动作 |
|-----------|------|------|
| 0 | 成功 | 解析 stdout JSON |
| 1 | HTTP/运行时错误 | 读 stderr `error` / `status` / `url` |
| 2 | 参数/资源无效 | 读 `did_you_mean`，修正后重试 |

## 示例

更多端到端示例见 [examples.md](examples.md)。
