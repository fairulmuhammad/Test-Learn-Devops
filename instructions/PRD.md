# Product Requirements Document (PRD)
## Multi-Agent AI Orchestration System

**Version:** 1.0.0  
**Date:** 2026-07-31  
**Status:** Draft → Implementation  
**Owner:** Infrastructure Team  
**Stack:** 9router (Model Router) + Hermes Agent (CLI Orchestrator) + MCP Servers

---

## 1. Overview

### 1.1 Problem Statement
The current AI setup operates as a single monolithic agent. All tasks — planning, research, coding, and execution — run through one model instance with one tool context. This creates bottlenecks:
- **No parallelism:** Research and coding cannot happen simultaneously.
- **No role specialization:** The same model handles high-level architecture and low-level file grepping.
- **No cost optimization:** Expensive reasoning models are used for trivial lookups.
- **No isolation:** A failed code generation can corrupt the orchestrator's context.

### 1.2 Solution
Build a **multi-agent orchestration layer** on top of 9router and Hermes Agent that enables:
1. **Role-based agent specialization** (Planner, Researcher, Builder, Executor).
2. **Parallel subagent execution** with automatic result synthesis.
3. **Model routing per role** via 9router combos for cost/performance optimization.
4. **MCP server access inheritance** so subagents use all available tools.
5. **Nested orchestration** where subagents can spawn their own workers.

### 1.3 Goals
| ID | Goal | Priority |
|---|---|---|
| G1 | Achieve functional parity with Claude Code subagents and Kimi Code multi-agent | P0 |
| G2 | Reduce average task latency by 40% through parallelization | P0 |
| G3 | Reduce token cost by 60% by routing trivial tasks to cheap models | P1 |
| G4 | Support 5+ concurrent subagents without context pollution | P1 |
| G5 | Maintain 99% reliability with automatic retry and timeout handling | P2 |

### 1.4 Non-Goals
- **Not** building a custom orchestrator from scratch (use Hermes Agent's `delegate_task`).
- **Not** replacing 9router (use it for model routing).
- **Not** supporting non-MCP tool integrations (standardize on MCP).
- **Not** building a web UI (CLI-first, headless server deployment).

---

## 2. User Stories

### 2.1 As a developer, I want to research multiple topics in parallel
> "Research auth libraries, DB pooling, and Docker builds in parallel and give me a summary."

**Acceptance:**
- System spawns 3 Researcher subagents simultaneously.
- Each uses `research` (cheap, fast model).
- Results are synthesized into one markdown report.
- Total time < 1.5× slowest individual research task.

### 2.2 As a developer, I want a full build pipeline
> "Build an auth module with JWT, bcrypt, endpoints, and tests."

**Acceptance:**
- Planner subagent creates architecture and task breakdown.
- 4 Builder subagents run in parallel for independent components.
- Executor subagent runs tests and reports pass/fail.
- Orchestrator presents final result with file tree and test output.

### 2.3 As a developer, I want safe parallel file operations
> "Refactor all utility files to use ES modules."

**Acceptance:**
- System identifies independent files via path analysis.
- Builder subagents edit files in parallel where paths don't overlap.
- Conflicting edits are queued sequentially.
- Git diff is presented for review before any commit.

---

## 3. Functional Requirements

### 3.1 Agent Role System (FR-1 → FR-5)

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | System MUST support 4 primary roles: Orchestrator, Planner, Researcher, Builder, Executor | P0 |
| FR-2 | Each role MUST map to a specific 9router model combo | P0 |
| FR-3 | Orchestrator MUST be able to delegate tasks to any role via `delegate_task` | P0 |
| FR-4 | Subagents MUST inherit the parent agent's MCP toolsets when `inherit_mcp_toolsets: true` | P0 |
| FR-5 | Subagents MUST run in isolated terminal sessions to prevent state pollution | P1 |

### 3.2 Parallel Execution (FR-6 → FR-10)

| ID | Requirement | Priority |
|---|---|---|
| FR-6 | System MUST support up to 5 concurrent subagents (`max_concurrent_children: 5`) | P0 |
| FR-7 | Read-only tools (read_file, search_files, web_search) MUST execute in parallel automatically | P0 |
| FR-8 | Write tools on non-overlapping paths MUST execute in parallel | P1 |
| FR-9 | Write tools on overlapping paths MUST be sequentialized with conflict detection | P1 |
| FR-10 | MCP tools from servers with `supports_parallel_tool_calls: true` MUST execute in parallel | P1 |

### 3.3 Model Routing (FR-11 → FR-14)

| ID | Requirement | Priority |
|---|---|---|
| FR-11 | 9router MUST expose 4 combos: `plan`, `research`, `code`, `cheap` | P0 |
| FR-12 | Orchestrator MUST default to the main model (currently `premium-reques`) | P0 |
| FR-13 | Subagents MUST default to `research` via `delegation.model` | P0 |
| FR-14 | Model selection MUST be transparent (logged per subagent spawn) | P2 |

> **Reality check (2026-07-31):** combo names CANNOT contain `:` (9router rejects with 400). Per-role model routing is NOT supported — `delegation.model` is a single value applied to ALL subagents. Every child uses the same combo; role differentiation is via toolsets + prompts only.

### 3.4 Nested Orchestration (FR-15 → FR-17)

| ID | Requirement | Priority |
|---|---|---|
| FR-15 | Subagents MUST be able to spawn their own subagents up to `max_spawn_depth: 2` | P1 |
| FR-16 | Nested orchestration MUST prevent infinite recursion (depth hard limit) | P0 |
| FR-17 | Parent agents MUST receive structured results from all children | P1 |

### 3.5 MCP Integration (FR-18 → FR-21)

| ID | Requirement | Priority |
|---|---|---|
| FR-18 | System MUST support 5+ MCP servers: Filesystem, GitHub, Browser, PostgreSQL, Custom API | P0 |
| FR-19 | MCP servers MUST be hot-reloadable without restarting Hermes | P2 |
| FR-20 | Failed MCP server connections MUST degrade gracefully (exclude tools, log warning) | P1 |
| FR-21 | MCP tool results MUST be included in subagent context windows | P0 |

---

## 4. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | End-to-end latency for 5 parallel research tasks | < 30s |
| NFR-2 | Subagent spawn overhead | < 2s |
| NFR-3 | Context window efficiency (no duplicate system prompts) | < 20% overhead |
| NFR-4 | Token cost reduction vs single-agent monolith | > 50% |
| NFR-5 | Uptime (excluding model provider outages) | > 99% |
| NFR-6 | Maximum subagent timeout | 600s |
| NFR-7 | Configuration reload without restart | < 5s |

---

## 5. Agent Role Specifications

### 5.1 Orchestrator (Master Agent)
- **Model:** main model (`premium-reques` combo via `custom:wannadev`)
- **Identity:** Defined in `~/.hermes/SOUL.md`
- **Responsibilities:**
  - Parse user intent and classify task complexity
  - Decide whether to delegate or handle directly
  - Spawn Planner for architecture-heavy tasks
  - Fan out Researcher/Builder/Executor subagents
  - Synthesize results from all children
  - Handle failures and retries
- **Tools:** `delegate_task`, `read_file`, `search_files`, `todo`, `memory`
- **Output Format:** Structured markdown with task tree and final synthesis

### 5.2 Planner (Subagent)
- **Model:** `plan` (via `delegation.model` — same for all children)
- **Role Type:** `orchestrator` (can spawn further subagents)
- **Responsibilities:**
  - Decompose complex tasks into atomic subtasks
  - Define dependencies between subtasks (DAG)
  - Specify which role should handle each subtask
  - Estimate iteration counts and timeouts
- **Tools:** `read_file`, `search_files`, `web_search`, `delegate_task`
- **Output Format:** JSON or markdown task list with `task_id`, `role`, `dependencies`, `description`

### 5.3 Researcher (Subagent)
- **Model:** `research` (via `delegation.model`)
- **Role Type:** `leaf` (no further delegation)
- **Responsibilities:**
  - Gather information from codebase, web, documentation
  - Search for patterns, libraries, best practices
  - Summarize findings with sources
- **Tools:** `read_file`, `search_files`, `web_search`, `web_extract`, `browser_tool`
- **Output Format:** Markdown summary with source citations

### 5.4 Builder (Subagent)
- **Model:** `research` combo by default (see delegation.model note; `code` combo exists for manual model swaps)
- **Role Type:** `leaf`
- **Responsibilities:**
  - Write, modify, and refactor code
  - Create files and directories
  - Implement features according to specification
- **Tools:** `read_file`, `write_file`, `patch`, `terminal_tool`, `code_execution`
- **Output Format:** List of modified files with diffs

### 5.5 Executor (Subagent)
- **Model:** `research` combo by default (same note as Builder)
- **Role Type:** `leaf`
- **Responsibilities:**
  - Run commands, tests, builds, deployments
  - Verify that code works correctly
  - Report logs, errors, and success metrics
- **Tools:** `terminal_tool`, `code_execution`, `process_registry`
- **Output Format:** Command output, exit codes, test results

---

## 6. Tool & MCP Inventory

### 6.1 Native Hermes Toolsets
| Toolset | Purpose | Parallel Safe |
|---|---|---|
| `core` | Basic agent operations | Yes |
| `terminal` | Shell command execution | No (stateful) |
| `file` | File read/write/search | Read: Yes / Write: Path-scoped |
| `web` | Web search and extraction | Yes |
| `browser` | Browser automation | No |
| `code_execution` | Run code in sandbox | No |
| `delegate` | Spawn subagents | N/A |
| `todo` | Task tracking | Yes |
| `memory` | Long-term memory | Yes |
| `skills` | Reusable skill modules | Yes |

### 6.2 MCP Servers
| Server | Package | Tools | Parallel Safe |
|---|---|---|---|
| `project_fs` | `@modelcontextprotocol/server-filesystem` | read, write, list, search | Read: Yes |
| `github` | `@modelcontextprotocol/server-github` | repo, issue, PR ops | No |
| `browser` | `@modelcontextprotocol/server-puppeteer` | navigate, screenshot, click | No |
| `postgres` | `@modelcontextprotocol/server-postgres` | query, schema | Read: Yes |
| `internal_api` | Custom REST MCP | CRUD endpoints | Configurable |

---

## 7. Success Metrics & KPIs

| Metric | Baseline (Single Agent) | Target (Multi-Agent) | Measurement |
|---|---|---|---|
| Avg. task completion time | 100% | ≤ 60% | Timer per task |
| Token cost per task | 100% | ≤ 40% | 9router billing logs |
| Failed task rate | 5% | ≤ 2% | Error log analysis |
| User satisfaction (parallel tasks) | N/A | ≥ 4.5/5 | Post-task survey |
| Context pollution incidents | 10% | 0% | Manual audit |

---

## 8. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Subagent timeout on long builds | Medium | High | `child_timeout_seconds: 600`, async background mode |
| Context window overflow with many parallel results | High | Medium | Stream summaries, not full outputs; use `memory` tool |
| Model provider rate limiting | High | Medium | 9router fallback combos; exponential backoff |
| File write conflicts in parallel builders | High | Low | Path-overlap detection in Hermes `file` toolset |
| MCP server crash breaks all subagents | Medium | Low | Graceful degradation; health checks; hot reload |

---

## 9. Glossary

| Term | Definition |
|---|---|
| **9router** | Self-hosted AI model router providing OpenAI-compatible API with combo-based model selection |
| **Hermes Agent** | CLI-based AI agent framework with toolsets, MCP support, and delegation |
| **MCP** | Model Context Protocol — standard for AI tool server integration |
| **Combo** | Named model configuration in 9router (e.g., `plan` → `oc/big-pickle`) |
| **Subagent** | Agent spawned by another agent via `delegate_task` |
| **Leaf Agent** | Subagent that cannot spawn further subagents (terminal node) |
| **Orchestrator Agent** | Subagent that can spawn further subagents (non-terminal node) |
| **Fan Out** | Parallel delegation of multiple independent subtasks |
| **Synthesize** | Combining results from multiple subagents into a coherent output |

---

## 10. Appendix: Related Documents

- `ARCHITECTURE.md` — Technical architecture and data flows
- `AGENTS.md` — Detailed agent role definitions and protocols
- `MCP.md` — MCP server registry and tool catalog
- `WORKFLOWS.md` — Common workflow patterns with examples
- `PROMPTS.md` — System prompts and user prompt templates
- `SETUP.md` — Installation, configuration, and validation guide
