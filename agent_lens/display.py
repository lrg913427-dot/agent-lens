"""Rich 终端美化输出"""

from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


def format_tokens(n: int | float) -> str:
    """格式化 token 数量。"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(int(n))


def format_cost(usd: float | None) -> str:
    """格式化成本。"""
    if usd is None:
        return "—"
    if usd < 0.01:
        return f"${usd:.4f}"
    if usd < 1:
        return f"${usd:.3f}"
    return f"${usd:.2f}"


def format_latency(ms: int) -> str:
    """格式化延迟。"""
    if ms >= 60_000:
        return f"{ms/60_000:.1f}m"
    if ms >= 1_000:
        return f"{ms/1_000:.1f}s"
    return f"{ms}ms"


def format_timestamp(ts: float) -> str:
    """格式化时间戳。"""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    
    if dt.date() == now.date():
        return dt.strftime("%H:%M:%S")
    return dt.strftime("%m-%d %H:%M")


def format_status(status: str) -> Text:
    """格式化状态。"""
    if status == "ok":
        return Text("✓", style="green")
    return Text("✗", style="red")


def render_stats_table(stats: list[dict], group_by: str = "model"):
    """渲染统计表格。"""
    table = Table(
        title=f"Agent Lens — 按 {group_by} 统计",
        box=box.ROUNDED,
        show_lines=True,
    )
    
    table.add_column(group_by, style="cyan", min_width=20)
    table.add_column("调用次数", justify="right", style="bold")
    table.add_column("输入 Token", justify="right")
    table.add_column("输出 Token", justify="right")
    table.add_column("总 Token", justify="right", style="bold")
    table.add_column("成本 (USD)", justify="right", style="green")
    table.add_column("平均延迟", justify="right")
    table.add_column("错误", justify="right", style="red")
    
    total_cost = 0.0
    total_tokens = 0
    total_calls = 0
    total_errors = 0
    
    for row in stats:
        cost = row.get("total_cost_usd") or 0
        tokens = row.get("total_tokens") or 0
        calls = row.get("call_count") or 0
        errors = row.get("error_count") or 0
        
        total_cost += cost
        total_tokens += tokens
        total_calls += calls
        total_errors += errors
        
        avg_latency = row.get("avg_latency_ms") or 0
        
        table.add_row(
            str(row.get("group_key", "—")),
            str(calls),
            format_tokens(row.get("total_input_tokens") or 0),
            format_tokens(row.get("total_output_tokens") or 0),
            format_tokens(tokens),
            format_cost(cost),
            format_latency(int(avg_latency)),
            str(errors) if errors > 0 else "—",
        )
    
    # 合计行
    table.add_row(
        "[bold]合计[/bold]",
        f"[bold]{total_calls}[/bold]",
        "—",
        "—",
        f"[bold]{format_tokens(total_tokens)}[/bold]",
        f"[bold green]{format_cost(total_cost)}[/bold green]",
        "—",
        f"[bold red]{total_errors}[/bold red]" if total_errors > 0 else "—",
    )
    
    console.print(table)


def render_traces_table(traces: list[dict]):
    """渲染追踪记录表格。"""
    table = Table(
        title="最近调用",
        box=box.ROUNDED,
        show_lines=False,
    )
    
    table.add_column("时间", style="dim")
    table.add_column("状态", justify="center")
    table.add_column("模型", style="cyan", min_width=15)
    table.add_column("输入", justify="right")
    table.add_column("输出", justify="right")
    table.add_column("成本", justify="right", style="green")
    table.add_column("延迟", justify="right")
    
    for t in traces:
        table.add_row(
            format_timestamp(t["timestamp"]),
            format_status(t["status"]),
            t["model"] or "—",
            format_tokens(t["input_tokens"]),
            format_tokens(t["output_tokens"]),
            format_cost(t["cost_usd"]),
            format_latency(t["latency_ms"]),
        )
    
    console.print(table)


def render_summary(stats: dict):
    """渲染总览面板。"""
    calls = stats.get("call_count") or 0
    tokens = stats.get("total_tokens") or 0
    cost = stats.get("total_cost_usd") or 0
    avg_latency = stats.get("avg_latency_ms") or 0
    errors = stats.get("error_count") or 0
    input_tokens = stats.get("total_input_tokens") or 0
    output_tokens = stats.get("total_output_tokens") or 0
    
    lines = [
        f"[bold cyan]调用总数[/bold cyan]     {calls:,}",
        f"[bold cyan]总 Token[/bold cyan]      {format_tokens(tokens)}",
        f"  输入           {format_tokens(input_tokens)}",
        f"  输出           {format_tokens(output_tokens)}",
        f"[bold green]总成本[/bold green]       {format_cost(cost)}",
        f"[bold]平均延迟[/bold]     {format_latency(int(avg_latency))}",
    ]
    
    if errors > 0:
        lines.append(f"[bold red]错误数[/bold red]       {errors}")
    
    if calls > 0:
        cost_per_call = cost / calls
        tokens_per_call = tokens / calls
        lines.append(f"[dim]每调用成本[/dim]     {format_cost(cost_per_call)}")
        lines.append(f"[dim]每调用 Token[/dim]   {format_tokens(tokens_per_call)}")
    
    panel = Panel(
        "\n".join(lines),
        title="[bold]Agent Lens 总览[/bold]",
        border_style="blue",
    )
    console.print(panel)


def render_cost_report(stats: list[dict]):
    """渲染成本报告。"""
    if not stats:
        console.print("[dim]没有数据[/dim]")
        return
    
    table = Table(
        title="成本排行",
        box=box.ROUNDED,
    )
    
    table.add_column("#", style="dim", width=3)
    table.add_column("模型", style="cyan")
    table.add_column("成本", justify="right", style="green bold")
    table.add_column("调用", justify="right")
    table.add_column("Token", justify="right")
    table.add_column("占比", justify="right")
    
    total_cost = sum(r.get("total_cost_usd") or 0 for r in stats)
    
    for i, row in enumerate(stats[:15], 1):
        cost = row.get("total_cost_usd") or 0
        pct = (cost / total_cost * 100) if total_cost > 0 else 0
        
        # 进度条
        bar_width = 20
        filled = int(pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        table.add_row(
            str(i),
            row.get("group_key", "—"),
            format_cost(cost),
            str(row.get("call_count") or 0),
            format_tokens(row.get("total_tokens") or 0),
            f"{bar} {pct:.1f}%",
        )
    
    console.print(table)
