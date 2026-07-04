# Batch 0：建立專案骨架

## 目標

建立可開發、可測試、可擴充的 repo skeleton。

## Agent 任務

建立 `personal-rd-agent-os` 專案骨架，使用 `uv` + `pyproject.toml` 管理。

請建立以下結構：

```
configs/
docs/
src/rdos/
  cli/
  llm/
  graph/
  rag/
  schemas/
  trace/
  eval/
eval_sets/
sample_data/notes/
sample_data/expected_outputs/
data/lancedb/
data/sqlite/
data/traces/
data/reports/
tests/
scripts/
```

請加入基礎 dependencies：

- `langchain`
- `langgraph`
- `langchain-openai`
- `typer`
- `rich`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
- `lancedb`
- `pyyaml`
- `python-frontmatter`
- `markdown-it-py`
- `pytest`
- `ruff`
- `mypy`

同時建立：

- `README.md`
- `.env.example`
- `configs/models.yaml`
- `configs/privacy_policy.yaml`
- `configs/rag.yaml`
- `configs/tool_policy.yaml`

## 要求

1. 專案可執行 `pytest`
2. 專案可執行 `ruff check`
3. CLI entry point 為 `rdos`
4. 不需要實作功能，只建立乾淨骨架

## 驗收

```bash
uv run pytest
uv run ruff check .
uv run rdos --help
```

## 注意事項

- `pyproject.toml` 必須設定 `[project.scripts]` 的 `rdos = "rdos.cli:app"` entry point。
- 每個空資料夾加上 `.gitkeep`，避免 git 不追蹤。
- `src/rdos/__init__.py`、`src/rdos/cli/__init__.py` 等空 `__init__.py` 必須存在。
- `data/` 建議加入 `.gitignore`，但保留 `.gitkeep`。
- `.env.example` 至少包含 `OPENAI_API_KEY`、`LOCAL_LLM_BASE_URL`、`LOCAL_LLM_MODEL` 三個欄位範例。
- `configs/*.yaml` 可以是空 schema 或最小範例，後續 batch 會填入。
