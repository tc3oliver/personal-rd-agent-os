---
title: RAG Filtering 筆記
date: 2026-06-30
tags: [rag, retrieval, filtering]
privacy_level: private_raw
---

# RAG Filtering

Retrieval-Augmented Generation 的核心難題之一是 retrieved chunks 雜訊過多會稀釋 context，
讓模型容易產出幻覺或偏題。Filtering 是縮小 retrieved context 的重要手段。

## 為什麼需要 Filtering

當向量庫規模變大，single-stage semantic search 的 recall 高但 precision 通常不夠。
直接把 top-20 chunks 丟進 prompt 會稀釋注意力，導致答案模糊或被不相關內容帶偏。
Filtering 的目標是把 noise 削掉，留下真正與 query 相關的 chunk。

## 主要策略

### Metadata Filter

先用結構化欄位過濾：tag、date、folder、privacy_level。例如只搜 public 等級的 notes，
或只搜某段日期。Metadata filter 是最便宜也最可靠的 filtering，因為它是確定性的。

Metadata filter 適合用在「我知道我要找哪類資料」的情境，例如 daily digest 只看本週筆記。

### Semantic Filter

用 embedding 相似度做 second-stage filter。常見做法是先取 top-50，再用更精細的模型
（例如 cross-encoder） rerank 到 top-5。Cross-encoder 比 bi-encoder 貴但更準。

Semantic filter 適合「我不確定哪份筆記有答案，但我知道 query 的概念」這類開放式問題。

### Hybrid Filter

把 metadata filter 與 semantic filter 串接：先用 metadata 縮小候選集，再用 semantic 排序。
這是實務上最穩定的策略，因為它結合了結構性與語意性。

## 實作注意

Filtering 必須在 citation 之前完成，否則 citation 會被 noise 污染。Trace 應該記錄
每一階段的 chunk count，方便 debug「為什麼這個 chunk 沒被檢索到」。
