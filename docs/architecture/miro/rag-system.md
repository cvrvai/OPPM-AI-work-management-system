# RAG System Architecture — Miro Ready

Last updated: 2026-05-01

## Purpose

This document visualizes the **Retrieval-Augmented Generation (RAG) pipeline** in the Intelligence Service. Use it to understand how user queries become structured context for the LLM.

Each flowchart is:
- **Self-contained** — copy-paste into Miro
- **Color-coded by stage** — 🟦 Input, 🟩 Processing, 🟨 Retrieval, 🟥 Output
- **Mermaid-ready** — import directly or draw manually

---

## Table of Contents

1. [RAG Pipeline Overview](#1-rag-pipeline-overview)
2. [RAG Step-by-Step](#2-rag-step-by-step)
3. [Semantic Cache Flow](#3-semantic-cache-flow)
4. [Parallel Retrieval & Reranking](#4-parallel-retrieval--reranking)
5. [Project Context Builder](#5-project-context-builder)

---

## 1. RAG Pipeline Overview

**Purpose:** High-level view of how a user query becomes LLM context.

```mermaid
flowchart LR
    A["👤 User Query"] --> B["🛡️ Input Guardrail"]
    B --> C["✍️ Query Rewrite"]
    C --> D["🔢 Embedding"]
    D --> E{"🔍 Semantic Cache?"}
    E -- HIT --> F["📋 Cached Context"]
    E -- MISS --> G["🏷️ Query Classification"]
    G --> H["🔍 Parallel Retrieval"]
    H --> I["📊 RRF Rerank"]
    I --> J["📈 Project Boost"]
    J --> K["📝 Format Context"]
    K --> L["💾 Store Cache"]
    L --> M["📋 Retrieval Result"]
    F --> N["🧠 LLM Prompt"]
    M --> N
```

### Miro Tips
- Draw as **horizontal pipeline** (left to right)
- Use **diamond** for cache decision
- Show **shortcut arrow** (cache hit skips retrieval)

---

## 2. RAG Step-by-Step

**Purpose:** Detailed breakdown of each pipeline stage.

```mermaid
flowchart TD
    A["📝 Raw Query Text"] --> B["Step 1: Input Guardrail\nblock injection, > 4000 chars"]
    B --> C["Step 2: Query Rewrite\nLLM expands vague queries"]
    C --> D["Step 3: Generate Embedding\nvector for cache + retrieval"]
    D --> E{"Step 4: Semantic Cache\ncosine ≥ 0.92?"}
    E -- HIT --> F["✅ Return Cached Context\nskip retrieval"]
    E -- MISS --> G["Step 5: Classify Query\nlabel retriever types"]
    G --> H["Step 6: Parallel Retrieval\nvector + keyword + structured"]
    H --> I["Step 7: RRF Reranker\nReciprocal Rank Fusion"]
    I --> J["Step 8: Project Boost\nup-rank project-specific hits"]
    J --> K["Step 9: Format Context\nbuild retrieval string"]
    K --> L["Step 10: Store in Cache\nTTL 300s, ai:sem_cache: prefix"]
    L --> M["📋 Return Context to Caller"]
    F --> M
```

### Miro Tips
- Number each step **1-10**
- Use **decision diamond** for cache hit
- Show **shortcut path** (cache hit skips steps 5-10)

---

## 3. Semantic Cache Flow

**Purpose:** How Redis semantic cache avoids redundant retrieval.

```mermaid
flowchart TD
    A["🔢 Query Embedding"] --> B["🔍 Redis Lookup\nAI:SEM_CACHE:*"]
    B --> C{"Cosine Similarity\n≥ 0.92?"}
    C -- YES --> D["📋 Return Cached Context"]
    C -- NO --> E["🔍 Run Full Retrieval"]
    E --> F["📝 Format New Context"]
    F --> G["💾 Store in Redis\nTTL 300s"]
    G --> H["📋 Return New Context"]
    D --> I["🧠 LLM Prompt"]
    H --> I
```

### Miro Tips
- Show **Redis** as external database icon
- Highlight **threshold** (0.92) on decision diamond
- Show **TTL 300s** on cache store

---

## 4. Parallel Retrieval & Reranking

**Purpose:** How three retrievers work together and merge results.

```mermaid
flowchart TD
    A["🏷️ Classified Query"] --> B["🔍 Vector Retriever\npgvector similarity"]
    A --> C["🔍 Keyword Retriever\nfull-text search"]
    A --> D["🔍 Structured Retriever\ntable filters"]
    B --> E["📄 RetrievedChunks"]
    C --> E
    D --> E
    E --> F["📊 RRF Reranker\nReciprocal Rank Fusion"]
    F --> G["📈 Project Boost\nup-rank if project_id match"]
    G --> H["📝 Format Context String"]
    H --> I["📋 Final Retrieval Result"]
```

### Miro Tips
- Show **3 parallel boxes** for retrievers
- Merge into **single funnel** for RRF
- Show **project boost** as extra step after merge

---

## 5. Project Context Builder

**Purpose:** How project-scoped chat loads structured data into the LLM context window.

```mermaid
flowchart TD
    A["📡 POST /projects/:id/ai/chat"] --> B["🟩 Intelligence Service"]
    B --> C["📋 Load Project Metadata"]
    C --> D["📋 Load Objectives + Sub-Objectives"]
    D --> E["📋 Load Tasks + Assignees + Dependencies"]
    E --> F["📋 Load Costs + Risks + Deliverables"]
    F --> G["📋 Load Team + Skills"]
    G --> H["📋 Load Recent Commits + Analyses"]
    H --> I{"📝 Context Budget\n≤ 32000 chars?"}
    I -- YES --> J["📝 Build System Prompt"]
    I -- NO --> K["✂️ Trim by Tier\nT3 → T2 → T1"]
    K --> J
    J --> L["🧠 LLM Call"]
```

### Miro Tips
- Show **6 data sources** as stacked boxes
- Use **decision** for budget check
- Show **trimming** as fallback path

---

## Miro Import Guide

### Option 1: Mermaid Import (Fastest)

1. Open Miro
2. Add **Mermaid chart** widget
3. Copy-paste any Mermaid block above
4. Miro auto-generates the diagram

### Option 2: Manual Drawing (Most Control)

1. Use **4 colors** for stages:
   - 🟦 Blue = Input / Guardrails
   - 🟩 Green = Processing / Transform
   - 🟨 Yellow = Retrieval / Cache
   - 🟥 Red = Output / LLM
2. Add **emoji icons** for visual clarity
3. Use **decision diamonds** for yes/no branches
4. Label **all arrows** with action names
