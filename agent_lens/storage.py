"""SQLite 存储层"""

import sqlite3
import json
import time
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, asdict


DB_PATH = Path.home() / ".agent-lens" / "traces.db"


@dataclass
class Trace:
    """一次 API 调用记录。"""
    id: int | None = None
    timestamp: float = 0.0
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int = 0
    status: str = "ok"  # ok / error
    error_message: str = ""
    agent_name: str = ""
    session_id: str = ""
    tags: str = ""  # JSON array
    metadata: str = ""  # JSON object


def _get_db_path() -> Path:
    """获取数据库路径，确保目录存在。"""
    db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@contextmanager
def get_connection():
    """获取数据库连接。"""
    conn = sqlite3.connect(str(_get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库表。"""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ok',
                error_message TEXT NOT NULL DEFAULT '',
                agent_name TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_model ON traces(model)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_name)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id)
        """)


def insert_trace(trace: Trace) -> int:
    """插入一条追踪记录，返回 ID。"""
    if trace.timestamp == 0.0:
        trace.timestamp = time.time()
    if trace.total_tokens == 0:
        trace.total_tokens = trace.input_tokens + trace.output_tokens
    
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO traces (
                timestamp, provider, model, input_tokens, output_tokens,
                total_tokens, cost_usd, latency_ms, status, error_message,
                agent_name, session_id, tags, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace.timestamp, trace.provider, trace.model,
            trace.input_tokens, trace.output_tokens, trace.total_tokens,
            trace.cost_usd, trace.latency_ms, trace.status,
            trace.error_message, trace.agent_name, trace.session_id,
            trace.tags, trace.metadata,
        ))
        return cursor.lastrowid


def query_traces(
    limit: int = 50,
    offset: int = 0,
    model: str | None = None,
    agent: str | None = None,
    session: str | None = None,
    status: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[dict]:
    """查询追踪记录。"""
    conditions = []
    params = []
    
    if model:
        conditions.append("model LIKE ?")
        params.append(f"%{model}%")
    if agent:
        conditions.append("agent_name = ?")
        params.append(agent)
    if session:
        conditions.append("session_id = ?")
        params.append(session)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    if until:
        conditions.append("timestamp <= ?")
        params.append(until)
    
    where = " AND ".join(conditions) if conditions else "1=1"
    
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT * FROM traces
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()
        return [dict(r) for r in rows]


def get_stats(
    since: float | None = None,
    until: float | None = None,
    group_by: str = "model",
) -> list[dict]:
    """获取统计信息，按指定字段分组。"""
    conditions = []
    params = []
    
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    if until:
        conditions.append("timestamp <= ?")
        params.append(until)
    
    where = " AND ".join(conditions) if conditions else "1=1"
    
    valid_groups = {"model", "provider", "agent_name", "session_id", "status"}
    if group_by not in valid_groups:
        group_by = "model"
    
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT
                {group_by} as group_key,
                COUNT(*) as call_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd,
                AVG(latency_ms) as avg_latency_ms,
                MIN(latency_ms) as min_latency_ms,
                MAX(latency_ms) as max_latency_ms,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
            FROM traces
            WHERE {where}
            GROUP BY {group_by}
            ORDER BY total_cost_usd DESC
        """, params).fetchall()
        return [dict(r) for r in rows]


def get_total_stats(since: float | None = None) -> dict:
    """获取总计统计。"""
    conditions = []
    params = []
    
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    
    where = " AND ".join(conditions) if conditions else "1=1"
    
    with get_connection() as conn:
        row = conn.execute(f"""
            SELECT
                COUNT(*) as call_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd,
                AVG(latency_ms) as avg_latency_ms,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
            FROM traces
            WHERE {where}
        """, params).fetchone()
        return dict(row) if row else {}


def delete_traces(
    before: float | None = None,
    session: str | None = None,
) -> int:
    """删除追踪记录，返回删除数量。"""
    conditions = []
    params = []
    
    if before:
        conditions.append("timestamp < ?")
        params.append(before)
    if session:
        conditions.append("session_id = ?")
        params.append(session)
    
    if not conditions:
        return 0
    
    where = " AND ".join(conditions)
    
    with get_connection() as conn:
        cursor = conn.execute(f"DELETE FROM traces WHERE {where}", params)
        return cursor.rowcount
