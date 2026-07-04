# Batch 16：Real Research Apps — Digest + Topic + Synthesis

## 目標

RDOS 已有真實資料、真實模型、LangGraph runtime、tool gate。接下來做真正有用的 R&D apps：Daily Digest、Topic Explorer、Research Synthesis。

## Agent 任務

### 1. Daily Digest

```bash
rdos digest --since 2026-07-01 --collection clawd-research \
  --llm-mode local --embedding-provider local-bge-m3
```

輸出 markdown：

```markdown
# Daily R&D Digest - YYYY-MM-DD

## 新增主題
## 重點筆記
## 與既有研究關聯
## 可延伸成工作提案的方向
## 可寫成文章的題目
```

存到 `data/generated/digests/`。

### 2. Topic Explorer

```bash
rdos topic "AgentTrace" --collection clawd-research \
  --llm-mode local --embedding-provider local-bge-m3

rdos topic "知識與檢索" --since 2026-01-01 \
  --llm-mode local --embedding-provider local-bge-m3
```

輸出：

- topic map
- representative notes
- related topics
- timeline
- hot keywords
- blind spots
- suggested outputs

### 3. Research Synthesis

```bash
rdos synthesize "整理我關於 AgentTrace 與 agent flight recorder 的筆記" \
  --collection clawd-research \
  --llm-mode local --embedding-provider local-bge-m3
```

輸出：

```markdown
# Research Synthesis

## 核心結論
## 主要資料來源
## 技術脈絡
## 分歧觀點
## 可應用到 RDOS 的設計
## Citations
```

存到 `data/generated/reports/`。

### 4. Privacy Rule

因為 `clawd-research` 預設 `private_raw`：

- **local model only**
- 如果使用 cloud：必須 redaction + approval
- **這批先不要做 cloud escalation**

## 需求

1. 新增三個 CLI：`rdos digest` / `rdos topic` / `rdos synthesize`。
2. Daily Digest：
   - 找出指定日期後新增或修改的 notes
   - summarize each note
   - cluster common topics
   - retrieve related older notes
   - 輸出 markdown
   - 存到 `data/generated/digests/`
   - 寫 trace
3. Topic Explorer：
   - 支援 topic query
   - 回傳 representative notes / related topics / timeline / hot keywords / blind spots / suggested outputs
4. Research Synthesis：
   - 多輪 retrieval
   - context packing
   - citation-grounded synthesis（**每個 claim 都必須 cite**）
   - 輸出 markdown
   - 存到 `data/generated/reports/`
5. 所有 app 都必須：
   - 使用 effective privacy
   - 預設 local model
   - 不把 `private_raw` 送 external
   - 寫 trace
   - 走 structured output validation
   - 走 citation validation
6. 新增 schemas：`DigestOutput` / `TopicExplorerOutput` / `SynthesisOutput`。
7. 新增 smoke eval：
   - digest smoke eval
   - topic explorer smoke eval
   - synthesis citation coverage eval（每個 claim 是否都有 citation）
8. 不要做 Web UI。
9. 不要做 cloud escalation。
10. README 加入三個 app demo。

## 驗收

```bash
uv run pytest
uv run ruff check .

uv run rdos digest --since 2026-07-01 --collection clawd-research \
  --llm-mode local --embedding-provider local-bge-m3

uv run rdos topic "AgentTrace" --collection clawd-research \
  --llm-mode local --embedding-provider local-bge-m3

uv run rdos synthesize "整理我關於 AgentTrace 與 agent flight recorder 的筆記" \
  --collection clawd-research \
  --llm-mode local --embedding-provider local-bge-m3

uv run rdos trace list
```

## 驗收重點

這批做完，你要真的能問：

```bash
rdos synthesize "整理我關於 RAG evaluation 的筆記"
rdos topic "Context Engineering"
rdos digest --since 2026-07-01
```

## 完成後輸出

1. 修改檔案
2. 三個 app 的 workflow
3. output 範例路徑
4. citation validation 結果
5. 驗收結果
6. 下一個建議 batch

## Commit

```
feat(batch-16): add real research digest topic and synthesis apps
```
