"""导出功能 - CSV / JSON"""

import csv
import json
import io
from pathlib import Path
from datetime import datetime, timezone

from .storage import query_traces, get_stats


def export_csv(
    output: str | Path | None = None,
    model: str | None = None,
    agent: str | None = None,
    session: str | None = None,
    limit: int = 1000,
) -> str:
    """导出追踪记录为 CSV。返回文件路径或字符串。"""
    traces = query_traces(
        limit=limit,
        model=model,
        agent=agent,
        session=session,
    )
    
    if not traces:
        return ""
    
    fields = [
        "id", "timestamp", "provider", "model",
        "input_tokens", "output_tokens", "total_tokens",
        "cost_usd", "latency_ms", "status", "error_message",
        "agent_name", "session_id", "tags",
    ]
    
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    
    for t in traces:
        row = dict(t)
        # 格式化时间戳
        row["timestamp"] = datetime.fromtimestamp(
            row["timestamp"], tz=timezone.utc
        ).isoformat()
        writer.writerow(row)
    
    content = buf.getvalue()
    
    if output:
        path = Path(output)
        path.write_text(content, encoding="utf-8")
        return str(path)
    
    return content


def export_json(
    output: str | Path | None = None,
    model: str | None = None,
    agent: str | None = None,
    session: str | None = None,
    limit: int = 1000,
    pretty: bool = True,
) -> str:
    """导出追踪记录为 JSON。返回文件路径或字符串。"""
    traces = query_traces(
        limit=limit,
        model=model,
        agent=agent,
        session=session,
    )
    
    # 转换时间戳
    for t in traces:
        t["timestamp"] = datetime.fromtimestamp(
            t["timestamp"], tz=timezone.utc
        ).isoformat()
        # 解析 JSON 字段
        try:
            t["tags"] = json.loads(t["tags"])
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            t["metadata"] = json.loads(t["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    
    content = json.dumps(traces, indent=2 if pretty else None, ensure_ascii=False)
    
    if output:
        path = Path(output)
        path.write_text(content, encoding="utf-8")
        return str(path)
    
    return content


def export_stats_csv(
    output: str | Path | None = None,
    group_by: str = "model",
) -> str:
    """导出统计信息为 CSV。"""
    stats = get_stats(group_by=group_by)
    
    if not stats:
        return ""
    
    fields = [
        "group_key", "call_count",
        "total_input_tokens", "total_output_tokens", "total_tokens",
        "total_cost_usd", "avg_latency_ms", "min_latency_ms", "max_latency_ms",
        "error_count",
    ]
    
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(stats)
    
    content = buf.getvalue()
    
    if output:
        path = Path(output)
        path.write_text(content, encoding="utf-8")
        return str(path)
    
    return content
