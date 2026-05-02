"""模型定价数据 (USD per 1M tokens)"""

# 格式: {model_prefix: (input_price, output_price)}
PRICING = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-pro": (150.00, 600.00),
    "o3": (10.00, 40.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    
    # Anthropic
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-3.5-sonnet": (3.00, 15.00),
    "claude-3.5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    
    # Google
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    
    # DeepSeek
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    
    # Mistral
    "mistral-large": (2.00, 6.00),
    "mistral-small": (0.10, 0.30),
    
    # Qwen
    "qwen-max": (1.60, 6.40),
    "qwen-plus": (0.40, 1.20),
    "qwen-turbo": (0.05, 0.20),
    
    # Zhipu/GLM
    "glm-4": (7.14, 7.14),
    "glm-4-flash": (0.00, 0.00),
    
    # Xiaomi/MiMo
    "mimo-v2.5-pro": (0.28, 1.10),
    "mimo-v2.5": (0.14, 0.55),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """估算 API 调用成本 (USD)。返回 None 表示未知模型。"""
    model_lower = model.lower()
    
    # 精确匹配优先
    for prefix, (input_price, output_price) in PRICING.items():
        if model_lower.startswith(prefix):
            return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    
    return None


def list_models() -> list[tuple[str, float, float]]:
    """返回所有已知模型及其定价。"""
    return [(k, v[0], v[1]) for k, v in sorted(PRICING.items())]
