# agent-lens

AI Agent 追踪和成本优化 CLI 工具。

## 技术栈
- Python 3.10+
- click (CLI)
- rich (终端美化)
- SQLite (本地存储)

## 启动命令
```bash
pip install -e .
agent-lens stats
agent-lens report
```

## 部署
```bash
pip install build && python -m build
twine upload dist/*
```
