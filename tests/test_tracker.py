"""基础测试"""

import time
import pytest
from agent_lens.storage import init_db, get_total_stats, get_stats, query_traces, Trace, insert_trace
from agent_lens.pricing import estimate_cost
from agent_lens.tracker import AgentLens


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """使用临时数据库。"""
    import agent_lens.storage as storage
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    init_db()
    yield


def test_estimate_cost():
    """测试成本估算。"""
    cost = estimate_cost("gpt-4o", 1000, 500)
    assert cost is not None
    assert cost > 0
    
    # 未知模型返回 None
    assert estimate_cost("unknown-model", 1000, 500) is None


def test_insert_and_query():
    """测试插入和查询。"""
    insert_trace(Trace(
        timestamp=time.time(),
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        cost_usd=0.01,
        latency_ms=500,
    ))
    
    traces = query_traces(limit=10)
    assert len(traces) == 1
    assert traces[0]["model"] == "gpt-4o"


def test_stats():
    """测试统计。"""
    for i in range(5):
        insert_trace(Trace(
            timestamp=time.time(),
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=0.01,
            latency_ms=500 + i * 100,
        ))
    
    stats = get_stats(group_by="model")
    assert len(stats) == 1
    assert stats[0]["call_count"] == 5
    assert stats[0]["total_tokens"] == 7500


def test_tracker_record():
    """测试追踪器记录。"""
    lens = AgentLens(agent_name="test", auto_init=True)
    
    trace_id = lens.record(
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=500,
        latency_ms=500,
    )
    
    assert trace_id > 0
    
    total = get_total_stats()
    assert total["call_count"] == 1


def test_tracker_context_manager():
    """测试 Context Manager。"""
    lens = AgentLens(agent_name="test", auto_init=True)
    
    with lens.trace(model="gpt-4o") as t:
        t.input_tokens = 1000
        t.output_tokens = 500
    
    total = get_total_stats()
    assert total["call_count"] == 1
    assert total["total_tokens"] == 1500


def test_tracker_decorator():
    """测试装饰器。"""
    lens = AgentLens(agent_name="test", auto_init=True)
    
    mock_result = type("Result", (), {
        "usage": type("Usage", (), {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
        })(),
    })()
    
    @lens.track(model="gpt-4o")
    def call_api():
        return mock_result
    
    call_api()
    
    total = get_total_stats()
    assert total["call_count"] == 1
    assert total["total_input_tokens"] == 1000
