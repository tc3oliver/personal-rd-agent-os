---
title: Structured Output 筆記
date: 2026-07-03
tags: [llm, structured-output, pydantic]
privacy_level: public
---

# Structured Output

LLM 產出結構化輸出是 agent 系統的基礎。沒有結構化輸出，下游 node 就要不斷寫 regex parse，
非常脆弱。

## 主要方法

### JSON Mode

OpenAI 與大多數 OpenAI-compatible server 都支援 `response_format=json_object`。這強制
模型輸出合法 JSON，但不保證 schema。

### Function Calling

透過 tool schema 強制模型產生符合 schema 的物件。最可靠，但不是所有 server 都支援。

### Schema-Guided Prompting

在 prompt 裡放 JSON schema 範例，要求模型模仿。最 portable 但最不可靠。

## Validation + Retry

不論用哪種方法，都要在應用層用 Pydantic validate。Validation 失敗應該 retry once，
第二次失敗就回傳 structured error，不要 raise。Raise 會讓整個 workflow 崩潰。

## 公開範例

Pydantic 與 LangChain 都有 structured output 範例，可參考官方文件。
