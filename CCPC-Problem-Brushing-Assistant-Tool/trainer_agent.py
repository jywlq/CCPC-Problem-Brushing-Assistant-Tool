import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass
class TagStat:
    count: int = 0
    passed: int = 0
    total_time: float = 0.0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.count if self.count else 0.0

    @property
    def avg_time(self) -> float:
        return self.total_time / self.count if self.count else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取刷题记录，识别薄弱标签并生成 7 天训练计划 Markdown 报告。"
    )
    parser.add_argument("--input", default="sample_data.json", help="输入 JSON 路径")
    parser.add_argument("--output", default="REPORT.md", help="输出 Markdown 路径")
    return parser.parse_args()


def parse_passed(record: dict, idx: int) -> bool:
    if "passed" in record:
        if not isinstance(record["passed"], bool):
            raise ValueError(f"第 {idx} 条记录字段 passed 必须是布尔值。")
        return record["passed"]
    if "status" in record:
        status = str(record["status"]).strip().lower()
        if status in {"passed", "pass", "ac", "accepted", "ok", "true", "1"}:
            return True
        if status in {"failed", "fail", "wa", "wrong answer", "false", "0"}:
            return False
        raise ValueError(f"第 {idx} 条记录字段 status 无法识别: {record['status']!r}")
    raise ValueError(f"第 {idx} 条记录缺少 passed 或 status 字段。")


def normalize_record(record: dict, idx: int) -> Tuple[List[str], bool, float]:
    if not isinstance(record, dict):
        raise ValueError(f"第 {idx} 条记录必须是对象。")

    if "tags" in record:
        tags_raw = record["tags"]
        if not isinstance(tags_raw, list) or not tags_raw:
            raise ValueError(f"第 {idx} 条记录字段 tags 必须是非空数组。")
        tags = []
        for tag in tags_raw:
            tag_text = str(tag).strip()
            if not tag_text:
                raise ValueError(f"第 {idx} 条记录 tags 中存在空标签。")
            tags.append(tag_text)
    elif "tag" in record:
        tag_text = str(record["tag"]).strip()
        if not tag_text:
            raise ValueError(f"第 {idx} 条记录字段 tag 不能为空。")
        tags = [tag_text]
    else:
        raise ValueError(f"第 {idx} 条记录缺少 tags 或 tag 字段。")

    if "time_spent_minutes" in record:
        minutes_raw = record["time_spent_minutes"]
    elif "minutes" in record:
        minutes_raw = record["minutes"]
    else:
        raise ValueError(f"第 {idx} 条记录缺少 time_spent_minutes 或 minutes 字段。")
    try:
        minutes = float(minutes_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"第 {idx} 条记录耗时字段（time_spent_minutes/minutes）必须是数字。"
        ) from exc
    if minutes <= 0:
        raise ValueError(f"第 {idx} 条记录耗时字段（time_spent_minutes/minutes）必须大于 0。")

    passed = parse_passed(record, idx)
    return tags, passed, minutes


def load_records(input_path: str) -> List[Tuple[List[str], bool, float]]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    if not os.path.isfile(input_path):
        raise ValueError(f"输入路径不是文件: {input_path}")

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"输入 JSON 解析失败: {exc}") from exc

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
        records = payload["records"]
    else:
        raise ValueError("输入 JSON 顶层必须是数组，或包含 records 数组的对象。")

    if not records:
        raise ValueError("输入记录为空，无法生成计划。")

    normalized = []
    for i, record in enumerate(records, start=1):
        normalized.append(normalize_record(record, i))
    return normalized


def build_tag_stats(records: Sequence[Tuple[List[str], bool, float]]) -> Dict[str, TagStat]:
    stats: Dict[str, TagStat] = {}
    for tags, passed, minutes in records:
        for tag in tags:
            stat = stats.setdefault(tag, TagStat())
            stat.count += 1
            stat.passed += 1 if passed else 0
            stat.total_time += minutes
    return stats


def pick_weak_tags(stats: Dict[str, TagStat]) -> List[str]:
    if not stats:
        return []
    max_avg = max((s.avg_time for s in stats.values()), default=1.0) or 1.0
    scored = []
    for tag, stat in stats.items():
        time_ratio = stat.avg_time / max_avg
        score = (1 - stat.pass_rate) * 0.65 + time_ratio * 0.35
        scored.append((score, tag))
    scored.sort(key=lambda x: x[0], reverse=True)
    count = min(3, len(scored))
    if len(scored) >= 2:
        count = max(2, count)
    return [tag for _, tag in scored[:count]]


def build_seven_day_plan(all_tags: List[str], weak_tags: List[str]) -> List[Tuple[int, List[str]]]:
    if not all_tags:
        return []

    non_weak = [t for t in all_tags if t not in weak_tags]
    if not non_weak:
        non_weak = all_tags[:]

    weak_cursor = 0
    other_cursor = 0
    plan: List[Tuple[int, List[str]]] = []

    for day in range(1, 8):
        target_count = 2 if day % 2 == 1 else 3
        day_tags: List[str] = []

        if weak_tags:
            day_tags.append(weak_tags[weak_cursor % len(weak_tags)])
            weak_cursor += 1
        else:
            day_tags.append(all_tags[(day - 1) % len(all_tags)])

        while len(day_tags) < target_count:
            candidate = non_weak[other_cursor % len(non_weak)]
            other_cursor += 1
            if len(non_weak) > 1 and candidate in day_tags:
                continue
            day_tags.append(candidate)

        plan.append((day, day_tags))
    return plan


def render_report(
    input_path: str,
    records: Sequence[Tuple[List[str], bool, float]],
    stats: Dict[str, TagStat],
    weak_tags: List[str],
    plan: List[Tuple[int, List[str]]],
) -> str:
    total_records = len(records)
    total_passed = sum(1 for _, p, _ in records if p)
    overall_pass_rate = total_passed / total_records if total_records else 0.0
    avg_minutes = sum(m for _, _, m in records) / total_records if total_records else 0.0

    lines: List[str] = []
    lines.append("# 刷题训练报告")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 输入文件：`{input_path}`")
    lines.append(f"- 记录总数：**{total_records}**")
    lines.append(f"- 标签总数：**{len(stats)}**")
    lines.append(f"- 整体通过率：**{overall_pass_rate:.1%}**")
    lines.append(f"- 平均耗时：**{avg_minutes:.1f} 分钟/题**")
    lines.append("")
    lines.append("| 标签 | 题量 | 通过率 | 平均耗时(分钟) |")
    lines.append("| --- | ---: | ---: | ---: |")
    for tag in sorted(stats):
        stat = stats[tag]
        lines.append(
            f"| {tag} | {stat.count} | {stat.pass_rate:.1%} | {stat.avg_time:.1f} |"
        )
    lines.append("")
    lines.append("## 薄弱标签")
    lines.append("")
    if weak_tags:
        for tag in weak_tags:
            stat = stats[tag]
            lines.append(
                f"- **{tag}**：通过率 {stat.pass_rate:.1%}，平均耗时 {stat.avg_time:.1f} 分钟。"
            )
    else:
        lines.append("- 暂无可识别薄弱标签。")
    lines.append("")
    lines.append("## 7 天游计划表")
    lines.append("")
    lines.append("| 天数 | 计划题量 | 训练安排（每天至少 1 个薄弱标签） |")
    lines.append("| ---: | ---: | --- |")
    for day, day_tags in plan:
        items = [f"题{idx + 1}：`{tag}`" for idx, tag in enumerate(day_tags)]
        lines.append(f"| Day {day} | {len(day_tags)} | {'<br>'.join(items)} |")
    lines.append("")
    lines.append("## 备注建议")
    lines.append("")
    lines.append("- 薄弱标签优先做中等难度题，先保证正确率，再逐步提升速度。")
    lines.append("- 每天复盘 1 题错题，记录卡点与改进点。")
    lines.append("- 若连续两天通过率低于 50%，次日减少新题，增加同标签复盘。")
    lines.append("- 本计划为自动生成，可结合赛程与个人时间手动微调。")
    lines.append("")
    return "\n".join(lines)


def write_report(path: str, content: str) -> None:
    output_dir = os.path.dirname(os.path.abspath(path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    args = parse_args()
    try:
        records = load_records(args.input)
        stats = build_tag_stats(records)
        if not stats:
            raise ValueError("未提取到有效标签统计信息。")
        weak_tags = pick_weak_tags(stats)
        all_tags = sorted(stats.keys())
        plan = build_seven_day_plan(all_tags, weak_tags)
        report = render_report(args.input, records, stats, weak_tags, plan)
        write_report(args.output, report)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    print(f"[完成] 已生成报告：{args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
