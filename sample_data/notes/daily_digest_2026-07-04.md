---
title: Daily Digest 2026-07-04
date: 2026-07-04
tags: [journal, daily]
privacy_level: private_raw
---

# Daily Digest 2026-07-04

## 今日重點

早上研究了 RAG filtering 的 hybrid 策略，下午嘗試把 privacy routing 整合進 model router。
發現 effective privacy 的計算必須在 retrieve 之後，因為 chunk privacy 會影響最終等級。

## 個人想法

我覺得目前的 hybrid filter 還是太依賴 cross-encoder，token cost 偏高。或許可以用更小的
模型先做 first-stage rerank，再用大模型做 second-stage。

## 明天計畫

- 把 trace store 接上 agent loop
- 寫 eval set 的第一版 sample
- 試試本地 llama.cpp 的 enable_thinking 參數
