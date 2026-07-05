# Parking Lot — NOT planned for v1.0

> These items are **intentionally deferred**. They are not "TODO". They are not "coming soon". They are parked.

If any of them become necessary, they belong in a **new project**, not v1.x patches.

## External sources

- ❌ GitHub issues connector
- ❌ arXiv paper ingestion
- ❌ Hacker News clipping
- ❌ RSS / Atom feed ingestion
- ❌ Twitter / X scraping
- ❌ Slack / Discord archive ingestion

**Reason**: RDOS is a personal research assistant, not a content aggregator. Adding sources invites scope creep and ingestion-maintenance burden.

## Plugins

- ❌ Plugin architecture for external tools
- ❌ Marketplace / registry
- ❌ Third-party tool SDK

**Reason**: Tool permission gate is the trust boundary. Plugins would either bypass it or duplicate it.

## Web UI / mobile

- ❌ Web dashboard
- ❌ React / Vue frontend
- ❌ Mobile app (iOS / Android)
- ❌ Electron desktop wrapper

**Reason**: CLI-first is a feature, not a limitation. Web UI is a separate project if it ever happens.

## Auto code editing

- ❌ `run_shell` tool
- ❌ `git_push` tool
- ❌ Auto PR creation
- ❌ IDE integration (VS Code / JetBrains)
- ❌ Code modification agent

**Reason**: RDOS is a research assistant, not an automation framework. Auto-editing code crosses a trust boundary that v1.0 deliberately does not cross.

## Production multi-user

- ❌ Multi-tenant isolation
- ❌ User accounts / auth
- ❌ Shared corpus
- ❌ Production multi-user deployment

**Reason**: Single-user by design. Multi-tenant requires a different threat model, different storage, different everything.

## Knowledge graph rewrite

- ❌ Replace SQLite + LanceDB with Neo4j / NebulaGraph
- ❌ GraphRAG-style community detection
- ❌ Entity extraction pipeline

**Reason**: Hybrid retriever (RRF) on the current SQLite + LanceDB stack works (recall@5 = 0.73). Graph rewrite would be a research project, not an engineering improvement.

## Other

- ❌ `run_shell`, `git_push`, `send_email`, `delete_file` tools — out of scope **forever**
- ❌ Auto-purge of stale documents — stale markers preserve citation validity
- ❌ Cloud as default provider — local-first is the design
- ❌ Production SLA / SRE runbook — not production-grade

## What CAN happen post-v1.0

Only maintenance:

- ✅ Bug fixes (with regression tests)
- ✅ Security disclosures (file as private issues)
- ✅ Documentation clarifications (without changing behavior)
- ✅ Dependency updates (security patches only)

That's it. Everything else is a new project.
