"""CLI 命令入口"""

import time
import click
from rich.console import Console

from . import __version__
from .storage import init_db, get_total_stats, get_stats, query_traces, delete_traces
from .display import (
    console,
    render_stats_table,
    render_traces_table,
    render_summary,
    render_cost_report,
)
from .export import export_csv, export_json, export_stats_csv

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="agent-lens")
def cli():
    """Agent Lens — AI Agent 追踪和成本优化工具
    
    追踪 API 调用、分析 token 用量、优化成本。
    """
    init_db()


@cli.command()
@click.option("--today", is_flag=True, help="仅显示今日数据")
@click.option("--week", is_flag=True, help="仅显示本周数据")
@click.option("--month", is_flag=True, help="仅显示本月数据")
def stats(today, week, month):
    """显示总览统计。"""
    since = None
    if today:
        since = time.time() - 86400
    elif week:
        since = time.time() - 86400 * 7
    elif month:
        since = time.time() - 86400 * 30
    
    data = get_total_stats(since=since)
    if not data or data.get("call_count", 0) == 0:
        console.print("[dim]没有追踪数据。[/dim]")
        console.print("[dim]使用 agent-lens 的 track/trace 装饰器开始记录。[/dim]")
        return
    
    render_summary(data)


@cli.command()
@click.option("--by", type=click.Choice(["model", "provider", "agent_name", "session_id", "status"]),
              default="model", help="分组字段")
@click.option("--today", is_flag=True, help="仅显示今日数据")
@click.option("--week", is_flag=True, help="仅显示本周数据")
def report(by, today, week):
    """按模型/提供商分组统计。"""
    since = None
    if today:
        since = time.time() - 86400
    elif week:
        since = time.time() - 86400 * 7
    
    stats = get_stats(since=since, group_by=by)
    if not stats:
        console.print("[dim]没有数据[/dim]")
        return
    
    render_stats_table(stats, group_by=by)


@cli.command()
@click.option("--today", is_flag=True, help="仅显示今日数据")
def cost(today):
    """成本排行。"""
    since = None
    if today:
        since = time.time() - 86400
    
    stats = get_stats(since=since, group_by="model")
    render_cost_report(stats)


@cli.command()
@click.option("-n", "--limit", default=20, help="显示条数")
@click.option("-m", "--model", default=None, help="按模型筛选")
@click.option("-a", "--agent", default=None, help="按 Agent 筛选")
@click.option("-s", "--session", default=None, help="按会话筛选")
def recent(limit, model, agent, session):
    """显示最近的调用记录。"""
    traces = query_traces(
        limit=limit,
        model=model,
        agent=agent,
        session=session,
    )
    
    if not traces:
        console.print("[dim]没有记录[/dim]")
        return
    
    render_traces_table(traces)


@cli.command()
@click.option("-n", "--limit", default=20, help="显示条数")
def top(limit):
    """成本最高的调用。"""
    traces = query_traces(limit=limit)
    
    if not traces:
        console.print("[dim]没有记录[/dim]")
        return
    
    # 按成本排序
    traces.sort(key=lambda t: t.get("cost_usd") or 0, reverse=True)
    
    from rich.table import Table
    from rich import box
    from .display import format_cost, format_tokens, format_latency, format_timestamp
    
    table = Table(title="成本最高的调用", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("时间", style="dim")
    table.add_column("模型", style="cyan")
    table.add_column("输入", justify="right")
    table.add_column("输出", justify="right")
    table.add_column("成本", justify="right", style="green bold")
    table.add_column("延迟", justify="right")
    
    for i, t in enumerate(traces[:limit], 1):
        table.add_row(
            str(i),
            format_timestamp(t["timestamp"]),
            t["model"] or "—",
            format_tokens(t["input_tokens"]),
            format_tokens(t["output_tokens"]),
            format_cost(t["cost_usd"]),
            format_latency(t["latency_ms"]),
        )
    
    console.print(table)


@cli.command()
@click.option("--model", default=None, help="按模型筛选")
@click.option("--agent", default=None, help="按 Agent 筛选")
@click.option("--session", default=None, help="按会话筛选")
@click.option("-o", "--output", default=None, help="输出文件路径")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON 格式")
def export(model, agent, session, output, as_json):
    """导出追踪记录。"""
    if as_json:
        result = export_json(
            output=output, model=model, agent=agent, session=session
        )
    else:
        result = export_csv(
            output=output, model=model, agent=agent, session=session
        )
    
    if not result:
        console.print("[dim]没有数据可导出[/dim]")
        return
    
    if output:
        console.print(f"[green]✓ 已导出到 {result}[/green]")
    else:
        click.echo(result)


@cli.command()
@click.option("--before", type=float, help="删除此时间戳之前的记录")
@click.option("--session", default=None, help="删除指定会话的记录")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
def clean(before, session, yes):
    """清理旧的追踪记录。"""
    if not before and not session:
        console.print("[yellow]需要指定 --before 或 --session[/yellow]")
        return
    
    if not yes:
        click.confirm("确定要删除记录吗?", abort=True)
    
    count = delete_traces(before=before, session=session)
    console.print(f"[green]✓ 已删除 {count} 条记录[/green]")


@cli.command()
def version():
    """显示版本信息。"""
    console.print(f"agent-lens v{__version__}")


@cli.command()
def demo():
    """运行演示，生成示例数据。"""
    from .tracker import AgentLens
    import random
    
    console.print("[bold]Agent Lens 演示[/bold]")
    console.print("生成示例追踪数据...\n")
    
    lens = AgentLens(agent_name="demo-agent")
    
    models = [
        ("gpt-4o", 2500, 800),
        ("gpt-4o-mini", 1500, 400),
        ("claude-3.5-sonnet", 3000, 1000),
        ("deepseek-chat", 2000, 600),
        ("gemini-2.5-flash", 1800, 500),
    ]
    
    for i in range(20):
        model, base_in, base_out = random.choice(models)
        input_tokens = base_in + random.randint(-500, 500)
        output_tokens = base_out + random.randint(-200, 300)
        latency = random.randint(200, 5000)
        status = "ok" if random.random() > 0.1 else "error"
        
        lens.record(
            model=model,
            input_tokens=max(100, input_tokens),
            output_tokens=max(50, output_tokens),
            latency_ms=latency,
            status=status,
            tags=["demo"],
        )
    
    console.print("[green]✓ 已生成 20 条示例记录[/green]\n")
    
    # 显示统计
    data = get_total_stats()
    render_summary(data)
    console.print()
    
    stats = get_stats(group_by="model")
    render_stats_table(stats)
    console.print()
    console.print("[dim]运行 `agent-lens stats` 查看总览[/dim]")
    console.print("[dim]运行 `agent-lens recent` 查看最近调用[/dim]")
    console.print("[dim]运行 `agent-lens cost` 查看成本排行[/dim]")


if __name__ == "__main__":
    cli()
