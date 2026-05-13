#!/usr/bin/env python3
"""
AI内容创作工作流 - 基于 Flow Forge
Hermes 生成素材 → Claude Code 编写脚本 → Windsurf 构建页面 → WorkBuddy 审核
"""

import json
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Callable, Any, Optional
from enum import Enum
from datetime import datetime


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING = "waiting"  # 人工审核检查点
    SKIPPED = "skipped"


@dataclass
class StepResult:
    status: StepStatus
    output: Any = None
    error: str = ""
    duration_ms: int = 0
    agent: str = ""  # 执行该步骤的AI


@dataclass
class WorkflowState:
    workflow_id: str
    current_step: int = 0
    steps: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> "WorkflowState":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


class ContentCreatorWorkflow:
    """AI内容创作工作流引擎"""
    
    def __init__(self, name: str, state_dir: str = ".workflow"):
        self.name = name
        self.steps: list[tuple[str, Callable, dict]] = []
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.agents = {
            "hermes": "Hermes (主控 + 素材生成)",
            "claude_code": "Claude Code (脚本编写)",
            "windsurf": "Windsurf (页面构建)",
            "workbuddy": "WorkBuddy (团队审核)"
        }

    def add_step(
        self,
        name: str,
        func: Callable,
        agent: str = "hermes",
        retry: int = 0,
        condition: Optional[Callable] = None,
        checkpoint: bool = False,
        description: str = "",
    ):
        self.steps.append((name, func, {
            "retry": retry,
            "condition": condition,
            "checkpoint": checkpoint,
            "agent": agent,
            "description": description,
        }))

    def run(self, context: dict = None) -> WorkflowState:
        state = WorkflowState(
            workflow_id=self.name,
            context=context or {},
            started_at=time.time(),
        )

        for i, (name, func, opts) in enumerate(self.steps):
            state.current_step = i
            agent_name = opts["agent"]
            
            print(f"\n{'='*60}")
            print(f"📋 步骤 {i+1}/{len(self.steps)}: {name}")
            print(f"🤖 执行代理: {self.agents.get(agent_name, agent_name)}")
            print(f"📝 {opts.get('description', '')}")
            print('='*60)

            # 检查条件
            if opts["condition"] and not opts["condition"](state.context):
                print(f"⏭️  跳过: {name} (条件不满足)")
                state.steps[name] = StepResult(status=StepStatus.SKIPPED)
                continue

            # 人工审核检查点
            if opts["checkpoint"]:
                print(f"⏸️  检查点: {name} - 等待人工审核")
                state.steps[name] = StepResult(status=StepStatus.WAITING, agent=agent_name)
                state.save(self.state_dir / f"{self.name}.json")
                return state

            # 执行（带重试）
            for attempt in range(opts["retry"] + 1):
                start = time.monotonic()
                try:
                    result = func(state.context)
                    duration = int((time.monotonic() - start) * 1000)

                    if isinstance(result, StepResult):
                        state.steps[name] = result
                    else:
                        state.steps[name] = StepResult(
                            status=StepStatus.SUCCESS,
                            output=result,
                            duration_ms=duration,
                            agent=agent_name,
                        )

                    if state.steps[name].output:
                        state.context[name] = state.steps[name].output
                    
                    print(f"✅ 完成: {name} ({duration}ms)")
                    break

                except Exception as e:
                    duration = int((time.monotonic() - start) * 1000)
                    if attempt < opts["retry"]:
                        print(f"⚠️  步骤 {name} 失败 (尝试 {attempt + 1}), 重试中...")
                        time.sleep(2 ** attempt)
                    else:
                        print(f"❌ 步骤 {name} 失败: {e}")
                        state.steps[name] = StepResult(
                            status=StepStatus.FAILED,
                            error=str(e),
                            duration_ms=duration,
                            agent=agent_name,
                        )
                        state.finished_at = time.time()
                        state.save(self.state_dir / f"{self.name}.json")
                        return state

        state.finished_at = time.time()
        state.save(self.state_dir / f"{self.name}.json")
        return state


# ============================================
# 步骤实现函数
# ============================================

def fetch_ai_hotspots(ctx: dict) -> dict:
    """步骤1: 从 aihot.virxact.com 抓取AI热点"""
    import httpx
    from bs4 import BeautifulSoup
    
    url = "https://aihot.virxact.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    # 这里用browser抓取，因为直接请求可能403
    # 实际实现中会调用Hermes的browser工具
    print("🌐 正在抓取 aihot.virxact.com 热点...")
    
    # 模拟返回数据结构（实际会从网站解析）
    hotspots = {
        "source": "aihot.virxact.com",
        "fetched_at": datetime.now().isoformat(),
        "categories": {
            "精选": [],
            "AI日报": [],
            "公众号爆文": [],
        },
        "items": []  # 从网站解析的热点条目
    }
    
    return hotspots


def select_topics(ctx: dict) -> dict:
    """步骤2: AI选题 - 从热点中筛选最有价值的内容"""
    hotspots = ctx.get("fetch_ai_hotspots", {})
    target_platforms = ctx.get("target_platforms", ["公众号", "小红书"])
    content_style = ctx.get("content_style", "专业深度")
    
    # 选题逻辑：
    # 1. 热度排序
    # 2. 平台适配性
    # 3. 变现潜力
    # 4. 内容差异化
    
    selected = {
        "primary_topic": None,  # 主选题
        "secondary_topics": [],  # 备选
        "platform_strategy": {},  # 各平台策略
        "content_angles": [],  # 内容切入角度
    }
    
    return selected


def generate_content_draft(ctx: dict) -> dict:
    """步骤3: Hermes生成内容初稿"""
    topic = ctx.get("select_topics", {}).get("primary_topic")
    platform = ctx.get("target_platform", "公众号")
    style = ctx.get("content_style", "专业深度")
    
    # 根据平台生成不同风格的内容
    content_specs = {
        "公众号": {
            "title_format": "悬念式/数字式/对比式",
            "length": "2000-3000字",
            "structure": "引言-核心观点-案例分析-总结-行动号召",
            "tone": "专业但易懂，有洞察力",
        },
        "小红书": {
            "title_format": "emoji+关键词+数字",
            "length": "500-800字",
            "structure": "封面-标题-正文-标签",
            "tone": "活泼、有共鸣、实用",
        }
    }
    
    draft = {
        "platform": platform,
        "title": "",
        "subtitle": "",
        "content": "",
        "key_points": [],
        "call_to_action": "",
        "seo_keywords": [],
        "image_prompts": [],  # 用于ComfyUI生成配图
    }
    
    return draft


def refine_with_claude_code(ctx: dict) -> dict:
    """步骤4: Claude Code 深度加工内容"""
    draft = ctx.get("generate_content_draft", {})
    
    # Claude Code 负责：
    # 1. 深度分析和技术解读
    # 2. 数据验证和事实核查
    # 3. 代码示例生成（如适用）
    # 4. 结构优化
    
    refined = {
        "enhanced_content": "",
        "technical_insights": [],
        "data_visualizations": [],  # 图表建议
        "code_examples": [],
        "fact_check_status": "verified",
    }
    
    return refined


def generate_media_assets(ctx: dict) -> dict:
    """步骤5: ComfyUI生成配图/封面"""
    draft = ctx.get("generate_content_draft", {})
    refined = ctx.get("refine_with_claude_code", {})
    
    # 根据内容生成配图
    media_plan = {
        "cover_image": {
            "prompt": "",
            "style": "科技感、简洁、专业",
            "size": "公众号封面 900x383 / 小红书 1080x1440",
        },
        "content_images": [],  # 文章内配图
        "social_cards": [],  # 社交分享卡片
    }
    
    return media_plan


def build_windsurf_page(ctx: dict) -> dict:
    """步骤6: Windsurf构建展示页面"""
    content = ctx.get("refine_with_claude_code", {})
    media = ctx.get("generate_media_assets", {})
    
    # Windsurf负责：
    # 1. 构建内容预览页面
    # 2. 响应式设计
    # 3. SEO优化
    # 4. 分享链接生成
    
    page = {
        "preview_url": "",
        "html_content": "",
        "seo_meta": {},
        "share_links": {},
    }
    
    return page


def team_review_checkpoint(ctx: dict) -> dict:
    """步骤7: WorkBuddy团队审核（检查点）"""
    # 这是人工审核步骤，会暂停工作流
    # WorkBuddy负责：
    # 1. 内容质量审核
    # 2. 品牌调性检查
    # 3. 合规性审查
    # 4. 最终确认
    
    review = {
        "reviewer": "",
        "status": "pending",
        "comments": [],
        "approved_at": None,
    }
    
    return review


def publish_to_platforms(ctx: dict) -> dict:
    """步骤8: 发布到各平台"""
    content = ctx.get("refine_with_claude_code", {})
    media = ctx.get("generate_media_assets", {})
    platforms = ctx.get("target_platforms", ["公众号", "小红书"])
    
    publish_results = {}
    
    for platform in platforms:
        if platform == "公众号":
            # 微信公众号API发布
            publish_results["公众号"] = {
                "status": "published",
                "url": "",
                "published_at": datetime.now().isoformat(),
            }
        elif platform == "小红书":
            # 小红书发布
            publish_results["小红书"] = {
                "status": "published",
                "url": "",
                "published_at": datetime.now().isoformat(),
            }
    
    return publish_results


def track_performance(ctx: dict) -> dict:
    """步骤9: 数据追踪和分析"""
    published = ctx.get("publish_to_platforms", {})
    
    # 追踪指标：
    # - 阅读量/播放量
    # - 点赞/收藏/评论
    # - 转发/分享
    # - 粉丝增长
    # - 转化率（如有）
    
    metrics = {
        "tracked_at": datetime.now().isoformat(),
        "platforms": {},
        "summary": {
            "total_views": 0,
            "total_engagement": 0,
            "best_performing": None,
        },
    }
    
    return metrics


def optimize_next_content(ctx: dict) -> dict:
    """步骤10: 基于数据优化下一期内容"""
    metrics = ctx.get("track_performance", {})
    
    # 优化建议：
    # 1. 什么类型内容表现好
    # 2. 什么发布时间效果好
    # 3. 什么标题风格点击率高
    # 4. 用户反馈关键词
    
    optimization = {
        "content_insights": [],
        "timing_recommendations": [],
        "style_adjustments": [],
        "topic_suggestions": [],
    }
    
    return optimization


# ============================================
# 构建工作流
# ============================================

def build_content_workflow() -> ContentCreatorWorkflow:
    """构建完整的内容创作工作流"""
    
    workflow = ContentCreatorWorkflow("ai-content-creator")
    
    # 步骤1: 抓取热点
    workflow.add_step(
        "fetch_ai_hotspots",
        fetch_ai_hotspots,
        agent="hermes",
        retry=3,
        description="从 aihot.virxact.com 抓取最新AI热点"
    )
    
    # 步骤2: 选题
    workflow.add_step(
        "select_topics",
        select_topics,
        agent="hermes",
        description="AI智能选题，筛选最有价值的内容方向"
    )
    
    # 步骤3: 生成初稿
    workflow.add_step(
        "generate_content_draft",
        generate_content_draft,
        agent="hermes",
        description="根据选题生成内容初稿"
    )
    
    # 步骤4: Claude Code深度加工
    workflow.add_step(
        "refine_with_claude_code",
        refine_with_claude_code,
        agent="claude_code",
        description="Claude Code 深度分析、技术解读、数据验证"
    )
    
    # 步骤5: 生成配图
    workflow.add_step(
        "generate_media_assets",
        generate_media_assets,
        agent="hermes",
        description="ComfyUI生成封面、配图、社交卡片"
    )
    
    # 步骤6: Windsurf构建页面
    workflow.add_step(
        "build_windsurf_page",
        build_windsurf_page,
        agent="windsurf",
        description="构建内容预览页面和分享链接"
    )
    
    # 步骤7: 团队审核（检查点）
    workflow.add_step(
        "team_review",
        team_review_checkpoint,
        agent="workbuddy",
        checkpoint=True,
        description="WorkBuddy团队审核，质量把关"
    )
    
    # 步骤8: 发布
    workflow.add_step(
        "publish_to_platforms",
        publish_to_platforms,
        agent="hermes",
        description="发布到公众号和小红书"
    )
    
    # 步骤9: 数据追踪
    workflow.add_step(
        "track_performance",
        track_performance,
        agent="hermes",
        description="追踪阅读量、互动、转化等数据"
    )
    
    # 步骤10: 优化下期
    workflow.add_step(
        "optimize_next_content",
        optimize_next_content,
        agent="hermes",
        description="基于数据反馈优化下一期内容策略"
    )
    
    return workflow


# ============================================
# 主程序
# ============================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🚀 AI内容创作工作流 - Content Creator Flow        ║
╠══════════════════════════════════════════════════════════════╣
║  代理协作链:                                                ║
║  Hermes (主控) → Claude Code → Windsurf → WorkBuddy         ║
║                                                              ║
║  执行流程:                                                   ║
║  1. 抓取热点 (aihot.virxact.com)                            ║
║  2. 智能选题                                                ║
║  3. 生成初稿 (Hermes)                                       ║
║  4. 深度加工 (Claude Code)                                  ║
║  5. 生成配图 (ComfyUI)                                      ║
║  6. 构建页面 (Windsurf)                                     ║
║  7. 团队审核 (WorkBuddy) ← 人工检查点                       ║
║  8. 多平台发布                                              ║
║  9. 数据追踪                                                ║
║  10. 优化迭代                                               ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 构建工作流
    workflow = build_content_workflow()
    
    # 初始上下文
    initial_context = {
        "hotspot_source": "https://aihot.virxact.com",
        "target_platforms": ["公众号", "小红书"],
        "content_style": "专业深度",
        "brand_voice": "AI领域权威、有洞察力、前瞻视角",
        "content_pillars": [
            "全球顶级AI机构动态",
            "前沿技术解读",
            "行业趋势分析",
            "实用工具推荐",
        ],
    }
    
    print("📋 工作流配置:")
    print(f"   - 热点来源: {initial_context['hotspot_source']}")
    print(f"   - 目标平台: {', '.join(initial_context['target_platforms'])}")
    print(f"   - 内容风格: {initial_context['content_style']}")
    print(f"   - 总步骤数: {len(workflow.steps)}")
    print()
    
    # 运行工作流
    print("▶️  开始执行工作流...\n")
    state = workflow.run(initial_context)
    
    # 输出结果
    print("\n" + "="*60)
    print("📊 执行结果:")
    print("="*60)
    
    for step_name, result in state.steps.items():
        status_emoji = {
            StepStatus.SUCCESS: "✅",
            StepStatus.FAILED: "❌",
            StepStatus.WAITING: "⏸️",
            StepStatus.SKIPPED: "⏭️",
            StepStatus.PENDING: "⏳",
            StepStatus.RUNNING: "🔄",
        }.get(result.status, "❓")
        
        agent_info = f" [{result.agent}]" if result.agent else ""
        print(f"{status_emoji} {step_name}{agent_info}")
        if result.error:
            print(f"   ❗ 错误: {result.error}")
    
    print(f"\n⏱️  总耗时: {state.finished_at - state.started_at:.1f}秒")
    print(f"💾 状态已保存: .workflow/{workflow.name}.json")
