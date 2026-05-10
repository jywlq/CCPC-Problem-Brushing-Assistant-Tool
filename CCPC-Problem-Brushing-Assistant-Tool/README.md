# CCPC-Problem-Brushing-Assistant-Tool

一个不依赖外部 AI 的 Python 小工具：读取刷题记录 JSON，统计标签情况，识别薄弱标签，并生成 7 天训练计划 Markdown 报告。

## 1. 环境要求

- Python 3.8+

## 2. 文件说明

- `trainer_agent.py`：主脚本
- `sample_data.json`：示例输入数据
- `REPORT.md`：脚本生成的报告（默认输出）

## 3. 使用方式

在仓库根目录执行：

```bash
python trainer_agent.py
```

默认等价于：

```bash
python trainer_agent.py --input sample_data.json --output REPORT.md
```

说明：脚本支持在任意目录执行。若 `--input` 使用相对路径，程序会先在当前目录查找，找不到时再到脚本所在目录查找。

### 命令行参数

- `--input`：输入 JSON 路径，默认 `sample_data.json`
- `--output`：输出 Markdown 路径，默认 `REPORT.md`

示例：

```bash
python trainer_agent.py --input my_records.json --output my_report.md
```

## 4. 输入 JSON 格式

支持两种顶层结构：

1) 直接是数组：`[ {...}, {...} ]`  
2) 对象中含 `records`：`{ "records": [ {...}, {...} ] }`

每条记录最小字段（与计划一致）：

- `title`：题目名（字符串）
- `tag`：标签（字符串）
- `passed`：是否通过（布尔值）
- `minutes`：耗时（正数）

示例：

```json
{
  "records": [
    {"title": "A", "tag": "DP", "passed": true, "minutes": 45},
    {"title": "B", "tag": "Greedy", "passed": false, "minutes": 30}
  ]
}
```

兼容输入：

- `tags`（标签数组）也支持
- `time_spent_minutes`（耗时）也支持
- 通过状态可使用 `status`（如 `"passed"` / `"failed"` / `"ac"` / `"wa"`）

## 5. 输出内容

报告固定包含四段：

1. 概览
2. 薄弱标签
3. 7 天游计划表
4. 备注建议
