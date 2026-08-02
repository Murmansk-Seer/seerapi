# SeerAPI CLI 示例

以下示例假设已安装 `seerapi` 。所有输出为 stdout 上的 compact JSON。

## 1. 查精灵基础信息

```bash
seerapi resources
seerapi describe pet --fields id,name,base_stats
seerapi get pet 1 --fields id,name,base_stats
```

`describe` 默认 `--scope item`，返回实例字段 schema。`get` 输出对应字段的数据。

## 2. 浏览技能列表

```bash
seerapi list skill --fields id,name,power --limit 10
```

输出结构：

```json
{
  "count": 12345,
  "offset": 0,
  "limit": 10,
  "results": [{"id": 10001, "name": "...", "power": 40}],
  "next": {"offset": 10, "limit": 10, "expand": true}
}
```

需要更多时用 `next` 中的参数翻页：

```bash
seerapi list skill --offset 10 --limit 10 --fields id,name,power
```

## 3. 按中文名查技能

```bash
seerapi get-by-name skill "虚妄幻境"
```

返回 `{ "<id>": { ... }, ... }` 字典。同名技能可能有多条，需结合 `id`、`power`、`category` 等字段甄别。

## 4. 解析阵容中的技能石运行时 ID

```bash
seerapi resolve-skill 105025 --fields kind,skill_stone_runtime,skill_stone,selected_effect
```

`105025` 会解析为物理攻击类别、技能石 25 和第 5 种附加特效。该命令会先查询普通
技能，未命中后才解码技能石，因此不会把真实普通技能误判为技能石。

## 5. 资源名纠错

```bash
seerapi get pets 1
```

stderr（exit code 2）：

```json
{"error":"unknown resource","resource":"pets","hint":"run seerapi resources","did_you_mean":["pet"]}
```

修正为 `seerapi get pet 1`。

## 6. 查看分页结构 vs 实例字段

```bash
# 实例字段（默认，LLM 查数据时用）
seerapi describe pet --fields id,name

# 分页列表信封（通常不需要）
seerapi describe pet --scope list

# NamedData 包装（get-by-name 响应结构，仅 NamedModel）
seerapi describe skill --scope name
```

## 7. 人类可读输出

仅在需要人工查看时使用：

```bash
seerapi get pet 1 --pretty
```
