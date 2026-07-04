---
title: Privacy Routing 設計
date: 2026-07-01
tags: [privacy, routing, security]
privacy_level: company_sensitive
---

# Privacy Routing

Privacy routing 是 RDOS 的核心差異。它把隱私等級納入 model routing 決策，
確保敏感資料不會外流到 cloud model。

## 隱私等級

RDOS 定義四個等級，由低到高：

- public: 可公開
- private_summary: 個人摘要，可升級到 cloud 但需 user 確認
- private_raw: 原始筆記，禁止 cloud model
- company_sensitive: 公司內部資料，禁止 cloud model

## Effective Privacy

```
effective_privacy = max(
    user_query_privacy,
    retrieved_chunk_privacy,
    tool_result_privacy,
    memory_context_privacy,
    trace_context_privacy,
)
```

取 max 是因為只要任一個 input 是高敏感，整個 run 就應該被當成高敏感處理。

## 內部規範

我們的 internal guideline 規定 roadmap 草稿、績效評估、薪資討論都屬於 company_sensitive。
這些內容絕對不能進 cloud，即使是摘要也不行。Roadmap Q4 draft 目前放在內部 wiki。
