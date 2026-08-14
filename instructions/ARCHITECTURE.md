# Architecture Document
## Multi-Agent AI Orchestration System

**Version:** 1.0.0  
**Related:** `PRD.md`, `AGENTS.md`, `MCP.md`

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER (CLI / SSH)                               │
│                         "Build an auth module"                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HERMES AGENT — ORCHESTRATOR                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Identity: ~/.hermes/SOUL.md                                       │   │
│  │  Model: plan (claude-opus-4-7 / gpt-4.1)                     │   │
│  │  Tools: delegate_task, read_file, search_files, todo, memory       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DELEGATION ENGINE                                                  │   │
│  │  • max_concurrent_children: 5                                       │   │
│  │  • max_spawn_depth: 2                                               │   │
│  │  • ThreadPoolExecutor (8 workers) for parallel safe tools           │   │
│  │  • Path-overlap detection for write tools                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  PLANNER    │  │ RESEARCHER  │  │   BUILDER   │  │   EXECUTOR      │  │
│  │  (subagent) │  │ (subagent)  │  │  (subagent) │  │   (subagent)    │  │
│  │  plan │  │research│  │ code  │  │   code    │  │
│  │  role: orch │  │ role: leaf  │  │  role: leaf │  │   role: leaf    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘  │
│         │                │                │                │                │
│         └────────────────┴────────────────┴────────────────┘                │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  MCP TOOL NETWORK                                                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │   │
│  │  │project_fs│ │  github  │ │ browser  │ │ postgres │ │internal │  │   │
│  │  │  (local) │ │  (cloud) │ │ (local)  │ │  (local) │ │  (api)  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              9ROUTER (localhost:20128)                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ plan  │ │research│ │ code  │ │    cheap      │   │
│  │  Reasoning  │ │   Search    │ │   Coding    │ │    Trivial          │   │
│  │  $$$/1M tok │ │  $$/1M tok  │ │  $$/1M tok  │ │    $/1M tok         │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
│                              │                                              │
│                    ┌─────────┴─────────┐                                    │
│                    ▼                   ▼                                    │
│            ┌─────────────┐    ┌─────────────┐                              │
│            │  Provider A │    │  Provider B │  (Fallback / Load Balance)   │
│            │ (OpenRouter)│    │  (Direct)   │                              │
│            └─────────────┘    └─────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

### 2.1 9router — Model Routing Layer

**Purpose:** Abstract model selection behind role-based combos.

**Responsibilities:**
- Expose OpenAI-compatible `/v1/chat/completions` endpoint at `localhost:20128`
- Route requests to `plan`/`research`/`code`/`cheap` aliases to actual model endpoints
- Handle fallback if a provider is down
- Log token usage per combo for cost tracking

**Combos (real, 2026-07-31 — colon names rejected by 9router):**
| Combo | Primary Model | Fallback | Use Case |
|---|---|---|---|
| `plan` | `oc/big-pickle` (deepseek-v4-flash) | `cf/@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` | Architecture, reasoning, orchestration |
| `research` | `oc/deepseek-v4-flash-free` | `cf/@cf/mistralai/mistral-small-3.1-24b-instruct` | Search, grep, documentation |
| `code` | `cf/@cf/qwen/qwen2.5-coder-32b-instruct` | `oc/big-pickle` | Code generation, refactoring |
| `cheap` | `cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast` | `oc/nemotron-3-ultra-free` | Summaries, trivial lookups |

**Interface:**
```
POST http://localhost:20128/v1/chat/completions
Headers: Authorization: Bearer <key>
Body: {
  "model": "plan",
  "messages": [...],
  "tools": [...]
}
```

### 2.2 Hermes Agent — Orchestration Engine

**Purpose:** Manage agent lifecycle, tool execution, and delegation.

**Key Modules:**

#### 2.2.1 Delegation Manager
- Maintains spawn tree (parent → children tracking)
- Enforces `max_concurrent_children` (default 5)
- Enforces `max_spawn_depth` (default 2)
- Routes subagent requests through 9router with role-specific combos

#### 2.2.2 Tool Parallelizer
- Classifies tools into:
  - `_PARALLEL_SAFE_TOOLS`: `read_file`, `search_files`, `web_search`, `todo`, `memory`
  - `_PATH_SCOPED_TOOLS`: `write_file`, `patch` (requires path-overlap check)
  - `_SEQUENTIAL_TOOLS`: `terminal_tool`, `browser_tool`, `code_execution`
- Uses `ThreadPoolExecutor(max_workers=8)` for safe batches
- File-write tools get serialized if paths overlap

#### 2.2.3 MCP Client
- Maintains persistent connections to MCP servers via stdio or HTTP
- Discovers tools via `tools/list` endpoint
- Injects tool definitions into agent context
- Handles server health checks and graceful degradation

#### 2.2.4 Context Manager
- Each subagent gets a fresh context window
- Parent context is NOT leaked to children (except via explicit task description)
- Child results are summarized before injection into parent context
- Uses `memory` tool for cross-session persistence

### 2.3 MCP Servers — Tool Ecosystem

**Purpose:** Provide external capabilities beyond native Hermes tools.

| Server | Transport | Tools | Parallel Support |
|---|---|---|---|
| `project_fs` | stdio (npx) | 4 | Read: Yes, Write: No |
| `github` | stdio (npx) | 10+ | No |
| `browser` | stdio (npx) | 5 | No |
| `postgres` | stdio (npx) | 3 | Read: Yes |
| `internal_api` | HTTP (SSE) | Custom | Configurable |

---

## 3. Data Flow Diagrams

### 3.1 Single Request (No Delegation)

```
User Input
    │
    ▼
┌─────────────────┐
│   Orchestrator  │──→ 9router (plan)
│   (Hermes)      │←── Response
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Tool Decision  │
└─────────────────┘
    │
    ├──→ Native Tool (read_file, etc.)
    │
    ├──→ MCP Server (project_fs, github, etc.)
    │
    └──→ Direct Response (no tool needed)
    │
    ▼
User Output
```

### 3.2 Parallel Research (Fan-Out)

```
User: "Research A, B, C in parallel"
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator (plan)              │
│  • Decides to fan out 3 Researcher tasks│
│  • Creates batch: [Research A, B, C]    │
└─────────────────────────────────────────┘
    │
    ├──→ delegate_task(task="Research A", model="research")
    │      │
    │      ▼
    │   ┌─────────────────┐
    │   │  Researcher-1   │──→ web_search, read_file, browser
    │   │  (research)│
    │   └─────────────────┘
    │      │
    │      ▼
    │   Result-A
    │
    ├──→ delegate_task(task="Research B", model="research")  [CONCURRENT]
    │      │
    │      ▼
    │   ┌─────────────────┐
    │   │  Researcher-2   │──→ web_search, read_file, browser
    │   │  (research)│
    │   └─────────────────┘
    │      │
    │      ▼
    │   Result-B
    │
    └──→ delegate_task(task="Research C", model="research")  [CONCURRENT]
           │
           ▼
        ┌─────────────────┐
        │  Researcher-3   │──→ web_search, read_file, browser
        │  (research)│
        └─────────────────┘
           │
           ▼
        Result-C
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator Synthesizes:              │
│  • Merges Result-A + B + C              │
│  • Removes duplicates                   │
│  • Formats as markdown report           │
└─────────────────────────────────────────┘
    │
    ▼
User: "Here is your research summary..."
```

### 3.3 Build Pipeline (Nested Orchestration)

```
User: "Build auth module with JWT, bcrypt, endpoints, tests"
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator (plan)              │
│  • Spawns Planner for architecture      │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Planner (plan, role=orch)        │
│  • Analyzes requirements                │
│  • Creates task DAG:                    │
│    1. JWT utility (independent)         │
│    2. Bcrypt helper (independent)       │
│    3. Endpoints (depends on 1,2)        │
│    4. Tests (depends on 3)              │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator receives plan             │
│  • Spawns Builder-JWT (parallel)        │
│  • Spawns Builder-Bcrypt (parallel)     │
└─────────────────────────────────────────┘
    │
    ├──→ Builder-JWT (code)
    │      │
    │      ▼
    │   write_file(src/auth/jwt.ts)
    │   Result: "Created jwt.ts"
    │
    └──→ Builder-Bcrypt (code)  [CONCURRENT]
           │
           ▼
        write_file(src/auth/bcrypt.ts)
        Result: "Created bcrypt.ts"
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator spawns Builder-Endpoints  │
│  (after JWT + Bcrypt complete)          │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Builder-Endpoints (code)         │
│  • Reads jwt.ts and bcrypt.ts           │
│  • Creates src/auth/endpoints.ts        │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator spawns Builder-Tests      │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Builder-Tests (code)             │
│  • Creates tests/auth.test.ts           │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Orchestrator spawns Executor           │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  Executor (code)                  │
│  • Runs: npm test                       │
│  • Reports: 4/4 passed                  │
└─────────────────────────────────────────┘
    │
    ▼
User: "✅ Auth module built. 4/4 tests passed."
```

---

## 4. State Management

### 4.1 Spawn Tree State

Hermes maintains an in-memory tree of all active subagents:

```
orchestrator_session_abc123
├── planner_001 (status: completed, result: "plan.md")
│   └── (no children — Planner returned plan text)
├── researcher_001 (status: completed, result: "research_A.md")
├── researcher_002 (status: completed, result: "research_B.md")
├── researcher_003 (status: running, started: 20s ago)
├── builder_001 (status: queued, waiting for: [researcher_003])
└── executor_001 (status: queued, waiting for: [builder_001])
```

**Persistence:**
- Active tree: In-memory only (lost on crash)
- Completed results: Saved to `~/.hermes/sessions/<id>/`
- Cross-session memory: `memory` tool writes to vector DB

### 4.2 File System State Isolation

| Isolation Level | Mechanism | Use Case |
|---|---|---|
| **Session** | Separate working directory per subagent | Default for all subagents |
| **Git Worktree** | `git worktree add` for major branches | Large refactors (manual opt-in) |
| **Docker** | Container per subagent | Untrusted code execution |

**Default:** Subagents share the host filesystem but operate in separate terminal sessions. File writes are subject to path-overlap detection.

---

## 5. Error Handling & Recovery

### 5.1 Subagent Failure Matrix

| Failure Type | Detection | Recovery | Escalation |
|---|---|---|---|
| **Timeout** (>600s) | Timer in Delegation Manager | Retry once with 2× timeout | Report to parent as partial failure |
| **Tool Error** | Tool result contains error | Retry with modified parameters | Parent decides to abort or re-delegate |
| **Model Error** (429, 500) | 9router response code | 9router auto-fallback to next model | Log to `~/.hermes/errors/` |
| **Context Overflow** | Token count > model limit | Summarize child results before injection | Split task into smaller subtasks |
| **MCP Disconnect** | Health check failure | Exclude server tools, retry connection | Degrade to native tools only |
| **Infinite Recursion** | Depth > `max_spawn_depth` | Hard block at Delegation Manager | Log and return error to parent |

### 5.2 Retry Policy

```yaml
retry:
  max_attempts: 3
  backoff: exponential
  base_delay_seconds: 2
  max_delay_seconds: 30
  retryable_errors:
    - "rate_limit"
    - "timeout"
    - "service_unavailable"
  non_retryable_errors:
    - "invalid_api_key"
    - "context_length_exceeded"
    - "content_policy_violation"
```

---

## 6. Security Model

### 6.1 Threat Surface

| Threat | Mitigation |
|---|---|
| Subagent executes destructive command | `subagent_auto_approve: false` — user must approve destructive ops |
| Subagent reads sensitive files | `project_fs` MCP scoped to `/home/user/projects` only |
| Subagent exfiltrates data via web | Web tools are read-only; no outbound POST from subagents |
| Token leak in logs | API keys stored in env vars, never in prompt context |
| Infinite cost loop | `max_iterations: 50`, `max_subagents: 10`, `child_timeout: 600s` |

### 6.2 Permission Model

```
Orchestrator:  Full access (can delegate anything)
Planner:       Can read all files, can delegate to Researchers
Researcher:    Read-only + web search (no file writes, no terminal)
Builder:       File write + terminal (restricted to project directory)
Executor:      Terminal only (can run tests, builds, deployments)
```

---

## 7. Performance Characteristics

### 7.1 Latency Budget (Parallel Research × 3)

| Stage | Time | Notes |
|---|---|---|
| Orchestrator decision | 2s | Model: plan |
| Subagent spawn overhead (×3) | 3s | 1s each, concurrent |
| Researcher execution (×3) | 15s | Parallel, limited by slowest |
| Result synthesis | 3s | Model: plan |
| **Total** | **~23s** | Baseline sequential: ~60s |

### 7.2 Cost Budget (Build Pipeline)

| Agent | Model | Tokens | Cost |
|---|---|---|---|
| Orchestrator | plan | 4K in / 2K out | $0.12 |
| Planner | plan | 3K in / 3K out | $0.15 |
| Builder-JWT | code | 2K in / 1.5K out | $0.03 |
| Builder-Bcrypt | code | 2K in / 1K out | $0.02 |
| Builder-Endpoints | code | 3K in / 2K out | $0.04 |
| Builder-Tests | code | 2K in / 1.5K out | $0.03 |
| Executor | code | 1K in / 0.5K out | $0.01 |
| **Total** | | | **~$0.40** |
| **Single-agent equivalent** | plan | 20K in / 15K out | **~$1.05** |
| **Savings** | | | **~62%** |

---

## 8. Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                         Server                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  9router (Docker / Systemd)                         │   │
│  │  Port: 20128                                        │   │
│  │  Config: /etc/9router/config.json                   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Hermes Agent (User process / Systemd)              │   │
│  │  Config: ~/.hermes/config.yaml                      │   │
│  │  Identity: ~/.hermes/SOUL.md                        │   │
│  │  Memory: ~/.hermes/memory/                          │   │
│  │  Sessions: ~/.hermes/sessions/                      │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MCP Servers (Child processes of Hermes)            │   │
│  │  • project_fs (stdio)                               │   │
│  │  • github (stdio)                                   │   │
│  │  • browser (stdio)                                  │   │
│  │  • postgres (stdio)                                 │   │
│  │  • internal_api (HTTP SSE)                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Change Log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-07-31 | Initial architecture for 9router + Hermes multi-agent orchestration |
