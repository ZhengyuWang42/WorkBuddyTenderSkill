---
name: tender-basic
description: Extract traceable tender project facts from one text PDF or DOCX and prepare the V1 review/output flow.
version: 0.1.0
---

# tender-basic

## Purpose

`tender-basic` is the minimal WorkBuddy Skill skeleton for the V1 flow:

```text
招标文件 → 项目事实 → 投标复核表 → 基础投标文件
```

## Current V1 scope

- Accept one text PDF or DOCX as the future input.
- Keep every resolved fact traceable to source evidence.
- Use `ProjectFacts` as the single source of truth for future JSON, XLSX, and DOCX outputs.
- Mark unresolved conflicts or ambiguity as `NEEDS_REVIEW`.
- Return `NOT_FOUND` instead of inventing a value.
- Detect scan-only PDF as `OCR_REQUIRED`; V1 does not implement OCR.

## Current implementation status

The local V1 implementation now supports deterministic document normalization,
fact extraction and resolution, ProjectFacts-based XLSX/DOCX generation, disk-artifact
Delivery QA, and a minimal one-command pipeline. WorkBuddy semantic conflict
arbitration is not implemented.

The local flow is:

```text
PDF/DOCX → normalized document → ProjectFacts → XLSX/DOCX → QA report
```

## Out of scope

No Web UI, FastAPI, database, RAG, vector store, Redis, Celery, Docker, OCR engine, external LLM client, Agent Framework, or unrelated abstraction layer is part of this Skill skeleton.
