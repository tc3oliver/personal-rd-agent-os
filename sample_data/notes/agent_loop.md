---
title: Agent Loop Pattern
date: 2026-07-02
tags: [agent, langgraph, pattern]
privacy_level: private_summary
---

# Agent Loop Pattern

Agent loop 的關鍵是把 reason → act → observe 變成可中斷、可 resume 的 state machine。
LangGraph 的 StateGraph + checkpoint 非常適合實作這個 pattern。

## State Design

State 應該是 immutable 的 TypedDict，每個 node 只更新自己負責的欄位。
避免「跨 node 互相改對方欄位」造成 race。

## Node Granularity

Node 太細會讓 graph 難維護；太粗會失去 interrupt/resume 的好處。實務上每個 node
應該對應一個語意清楚的步驟，例如 classify_task、retrieve、generate。

## Trace

每個 node 進入與離開都應該寫 trace，包含 input state hash、output state hash、latency。
Trace 是 debug agent loop 的唯一可靠手段。

## 我的草稿想法

之後想把 agent loop 套用到 daily digest：每天早上自動回顧昨日筆記，產出今日重點。
