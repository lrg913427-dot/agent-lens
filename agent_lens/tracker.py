"""核心追踪逻辑 - 装饰器和 Context Manager"""

import time
import uuid
import functools
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field

from .storage import Trace, insert_trace, init_db
from .pricing import estimate_cost


@dataclass
class TraceResult:
    """追踪结果。"""
    trace_id: int | None = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int = 0
    status: str = "ok"
    error: Exception | None = None


# 线程本地存储，用于嵌套追踪
_local = threading.local()


def _get_session_id() -> str:
    """获取或创建当前会话 ID。"""
    if not hasattr(_local, "session_id"):
        _local.session_id = uuid.uuid4().hex[:12]
    return _local.session_id


def set_session_id(session_id: str):
    """设置当前线程的会话 ID。"""
    _local.session_id = session_id


def new_session_id() -> str:
    """创建新的会话 ID 并设置为当前会话。"""
    sid = uuid.uuid4().hex[:12]
    _local.session_id = sid
    return sid


class AgentLens:
    """Agent Lens 追踪器。
    
    使用方式:
        # 作为装饰器
        @lens.track(model="gpt-4o")
        def call_api():
            ...
        
        # 作为 context manager
        with lens.trace(model="gpt-4o") as t:
            result = api_call()
            t.input_tokens = result.usage.prompt_tokens
            t.output_tokens = result.usage.completion_tokens
        
        # 直接记录
        lens.record(model="gpt-4o", input_tokens=100, output_tokens=50)
    """
    
    def __init__(self, agent_name: str = "", auto_init: bool = True):
        self.agent_name = agent_name
        if auto_init:
            init_db()
    
    def record(
        self,
        model: str = "",
        provider: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        cost_usd: float | None = None,
        status: str = "ok",
        error_message: str = "",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> int:
        """直接记录一条追踪。"""
        if cost_usd is None and input_tokens > 0:
            cost_usd = estimate_cost(model, input_tokens, output_tokens)
        
        trace = Trace(
            timestamp=time.time(),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            agent_name=self.agent_name,
            session_id=_get_session_id(),
            tags=__import__("json").dumps(tags or []),
            metadata=__import__("json").dumps(metadata or {}),
        )
        return insert_trace(trace)
    
    @contextmanager
    def trace(
        self,
        model: str = "",
        provider: str = "",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ):
        """Context Manager 方式追踪 API 调用。
        
        用法:
            with lens.trace(model="gpt-4o") as t:
                result = api_call()
                t.input_tokens = result.usage.prompt_tokens
                t.output_tokens = result.usage.completion_tokens
        """
        t = _TraceContext(model=model, provider=provider)
        start = time.monotonic()
        
        try:
            yield t
            t.status = "ok"
        except Exception as e:
            t.status = "error"
            t.error = str(e)
            raise
        finally:
            elapsed = int((time.monotonic() - start) * 1000)
            t.latency_ms = elapsed
            
            if t.cost_usd is None and t.input_tokens > 0:
                t.cost_usd = estimate_cost(t.model, t.input_tokens, t.output_tokens)
            
            trace = Trace(
                timestamp=time.time(),
                provider=provider or t.provider,
                model=t.model,
                input_tokens=t.input_tokens,
                output_tokens=t.output_tokens,
                total_tokens=t.input_tokens + t.output_tokens,
                cost_usd=t.cost_usd,
                latency_ms=t.latency_ms,
                status=t.status,
                error_message=t.error or "",
                agent_name=self.agent_name,
                session_id=_get_session_id(),
                tags=__import__("json").dumps(tags or []),
                metadata=__import__("json").dumps(metadata or {}),
            )
            t.trace_id = insert_trace(trace)
    
    def track(
        self,
        model: str = "",
        provider: str = "",
        tags: list[str] | None = None,
    ):
        """装饰器方式追踪函数调用。
        
        用法:
            @lens.track(model="gpt-4o")
            def call_api(prompt):
                return client.chat.completions.create(...)
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.trace(model=model, provider=provider, tags=tags) as t:
                    result = func(*args, **kwargs)
                    
                    # 尝试从 OpenAI-style 响应提取 token 用量
                    if hasattr(result, "usage") and result.usage:
                        t.input_tokens = getattr(result.usage, "prompt_tokens", 0) or 0
                        t.output_tokens = getattr(result.usage, "completion_tokens", 0) or 0
                    
                    return result
            return wrapper
        return decorator


@dataclass
class _TraceContext:
    """追踪上下文数据。"""
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int = 0
    status: str = "ok"
    error: str = ""
    trace_id: int | None = None


# 全局默认实例
_default_lens: AgentLens | None = None


def get_lens(agent_name: str = "default") -> AgentLens:
    """获取全局默认 AgentLens 实例。"""
    global _default_lens
    if _default_lens is None:
        _default_lens = AgentLens(agent_name=agent_name)
    return _default_lens


def record(**kwargs) -> int:
    """快捷方式：使用默认实例记录。"""
    return get_lens().record(**kwargs)


def trace(**kwargs):
    """快捷方式：使用默认实例追踪。"""
    return get_lens().trace(**kwargs)


def track(**kwargs):
    """快捷方式：使用默认实例装饰。"""
    return get_lens().track(**kwargs)
